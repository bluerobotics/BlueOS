import asyncio
import base64
import json
import os
import time
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple, cast

from aiodocker.exceptions import DockerError
from commonwealth.settings.manager import Manager
from loguru import logger

from config import DEFAULT_INJECTED_ENV_VARIABLES, SERVICE_NAME
from extension.exceptions import (
    ExtensionInsufficientStorage,
    ExtensionNotFound,
    ExtensionNotRunning,
    ExtensionPullFailed,
    IncompatibleExtension,
)
from extension.models import ExtensionSource
from harbor import ContainerManager, DockerCtx
from harbor.exceptions import ContainerNotFound
from manifest import ManifestManager
from manifest.models import ExtensionVersion
from settings import ExtensionSettings, SettingsV2
from utils import has_enough_disk_space


class Extension:
    """
    Extension class to manage extensions.
    """

    # If an extension is being installed the key will be the extension identifier if is being removed the key is the
    # container name.
    locked_entries: Dict[str, Literal[True]] = {}
    start_attempts: Dict[str, Tuple[int, int]] = {}

    _manager: Manager = Manager(SERVICE_NAME, SettingsV2)
    _settings = _manager.settings

    def __init__(self, source: ExtensionSource, digest: Optional[str] = None) -> None:
        self.source = source
        self.digest = digest

    @property
    def identifier(self) -> str:
        return self.source.identifier

    @property
    def tag(self) -> str:
        return self.source.tag

    @property
    def unique_entry(self) -> str:
        return f"{self.identifier}{self.tag}"

    @property
    def settings(self) -> ExtensionSettings:
        return cast(ExtensionSettings, self._fetch_settings(self.identifier, self.tag))

    @classmethod
    def lock(cls, key: str) -> None:
        cls.locked_entries[key] = True

    @classmethod
    def unlock(cls, key: str) -> None:
        cls.locked_entries.pop(key, None)

    @classmethod
    def mark_start_attempt(cls, key: str) -> None:
        if key not in cls.start_attempts:
            cls.start_attempts[key] = (0, 0)

        attempts, _ = cls.start_attempts[key]
        cls.start_attempts[key] = (attempts + 1, int(time.monotonic()))

    @classmethod
    def reset_start_attempt(cls, key: str) -> None:
        cls.start_attempts.pop(key, None)

    @classmethod
    def _fetch_settings(
        cls, identifier: Optional[str] = None, tag: Optional[str] = None
    ) -> List[ExtensionSettings] | ExtensionSettings:
        extensions: List[ExtensionSettings] = [
            ext
            for ext in cast(List[ExtensionSettings], cls._settings.extensions)
            if (identifier is None or ext.identifier == identifier) and (tag is None or ext.tag == tag)
        ]

        if identifier is not None and tag is not None:
            if not extensions:
                raise ExtensionNotFound(f"Extension {identifier}:{tag} not found")
            return extensions[0]
        return extensions

    def _save_settings(self, extension: Optional[ExtensionSettings] = None) -> None:
        self._settings.extensions = [
            other
            for other in self._settings.extensions
            if not (other.identifier == self.identifier and other.tag == self.tag)
        ]
        if extension:
            self._settings.extensions.append(extension)
        self._manager.save()

    def _set_container_config_default_env_variables(self, config: Dict[str, Any]) -> None:
        if "Env" not in config:
            config["Env"] = []

        existing_env_var_names = {entry.split("=", 1)[0] if "=" in entry else entry for entry in config["Env"]}

        for variable in DEFAULT_INJECTED_ENV_VARIABLES:
            env_val = os.getenv(variable)
            if variable not in existing_env_var_names and env_val:
                config["Env"].append(f"{variable}={env_val}")

    def _set_container_config_host_config(self, config: Dict[str, Any]) -> None:
        if "HostConfig" not in config:
            config["HostConfig"] = {}
        if "LogConfig" not in config["HostConfig"]:
            config["HostConfig"]["LogConfig"] = {}
        config["HostConfig"]["LogConfig"] = {"Type": "json-file", "Config": {"max-size": "20m", "max-file": "3"}}

    @classmethod
    async def remove(cls, container_name: str, delete_image: bool = True) -> None:
        try:
            logger.info(
                f"Removing extension {container_name} container" + ("and pruning image" if delete_image else "")
            )
            cls.lock(container_name)

            async with DockerCtx() as client:
                container = await ContainerManager.get_raw_container_by_name(client, container_name)

                image = container["Image"]

                await ContainerManager.kill_all_by_name(client, container_name)
                await container.delete()  # type: ignore
                logger.info(f"Extension {container_name} removed")

                if delete_image:
                    logger.info(f"Pruning image {image}")
                    await client.images.delete(image, force=True, noprune=False)
        finally:
            cls.unlock(container_name)

    async def _disable_running_extension(self) -> Optional["Extension"]:
        """Disable any currently running extension with the same identifier."""
        try:
            running_ext = await self.from_running(self.identifier)
            if running_ext:
                await running_ext.disable()
            return running_ext
        except (ExtensionNotRunning, ExtensionNotFound):
            return None

    def _create_extension_settings(self) -> ExtensionSettings:
        """Create and save extension settings."""
        new_extension = ExtensionSettings(
            identifier=self.identifier,
            name=self.source.name,
            docker=self.source.docker,
            tag=self.tag,
            permissions=self.source.permissions,
            enabled=True,
            user_permissions=self.source.user_permissions,
        )
        # Save in settings first, if the image fails to install it will try to fetch after in main kraken check loop
        # Atomic failure rolls this entry back and re-enables the previously running sibling.
        self._save_settings(new_extension)
        return new_extension

    def _prepare_docker_auth(self) -> Optional[str]:
        """Prepare Docker authentication string from source auth credentials."""
        if self.source.auth is None:
            return None
        docker_auth = f"{self.source.auth.username}:{self.source.auth.password}"
        return base64.b64encode(docker_auth.encode("utf-8")).decode("utf-8")

    @staticmethod
    async def _inspect_or_none(client: Any, ref: str) -> Optional[Any]:
        try:
            return await client.images.inspect(ref)
        except DockerError as error:
            if error.status == 404:
                return None
            raise

    async def _ensure_tagged_local_image(self, client: Any, sibling_image_id: Optional[str] = None) -> bool:
        # start() and a successful pull run docker:tag. Catalog platform digests are not
        # stored in RepoDigests after `docker pull repo:tag` (that records the index
        # digest), so a digest match against the catalog cannot be required.
        # sibling_image_id is only for the failed-pull fallback: a retag of the running
        # sibling onto the new name is not the requested version. Do not pass it after a
        # clean pull -- two tags can share an image Id (aliases) and still be the pull.
        tag_ref = f"{self.source.docker}:{self.tag}"
        tagged = await self._inspect_or_none(client, tag_ref)
        image_id = tagged.get("Id") if isinstance(tagged, dict) else None
        if isinstance(image_id, str) and image_id and (sibling_image_id is None or image_id != sibling_image_id):
            return True
        if not self.digest:
            return False
        digest = self.digest if self.digest.startswith("sha256:") else f"sha256:{self.digest}"
        digest_ref = f"{self.source.docker}@{digest}"
        info = await self._inspect_or_none(client, digest_ref)
        image_id = info.get("Id") if isinstance(info, dict) else None
        if not isinstance(image_id, str) or not image_id or image_id == sibling_image_id:
            return False
        try:
            await client.images.tag(digest_ref, self.source.docker, tag=self.tag)
        except Exception as error:
            logger.warning(f"Failed to tag {digest_ref} as {tag_ref}: {error}")
        tagged = await self._inspect_or_none(client, tag_ref)
        image_id = tagged.get("Id") if isinstance(tagged, dict) else None
        return (
            isinstance(image_id, str) and bool(image_id) and (sibling_image_id is None or image_id != sibling_image_id)
        )

    async def _rollback_failed_install(
        self,
        running_ext: Optional["Extension"],
        prior_settings: Optional[ExtensionSettings],
        atomic: bool,
    ) -> None:
        try:
            if prior_settings is not None:
                self._save_settings(prior_settings)
            elif atomic:
                self._save_settings()
            else:
                await self.set_enabled(False)
        except Exception as rollback_error:
            logger.warning(f"Failed to roll back {self.identifier}:{self.tag} after pull failure: {rollback_error}")
        if not running_ext:
            return
        try:
            self.reset_start_attempt(running_ext.unique_entry)
            await running_ext.enable()
        except Exception as enable_error:
            logger.warning(
                f"Failed to re-enable {running_ext.identifier}:{running_ext.tag} after pull failure: {enable_error}"
            )

    async def _pull_docker_image(self, docker_auth: Optional[str]) -> AsyncGenerator[bytes, None]:
        """Pull Docker image and yield progress updates."""
        tag = f"{self.source.docker}:{self.tag}" + (f"@{self.digest}" if self.digest else "")
        async with DockerCtx() as client:
            pull_ok = False
            async for line in client.images.pull(
                tag, repo=self.source.docker, tag=self.tag, auth=docker_auth, stream=True
            ):
                yield json.dumps(line).encode("utf-8")
                # Docker reports pull errors in-band; a finished stream without a success
                # status is not a completed pull.
                error = None
                status = None
                if isinstance(line, dict):
                    error = line.get("error") or (line.get("errorDetail") or {}).get("message")
                    status = line.get("status")
                if error:
                    raise RuntimeError(str(error))
                if isinstance(status, str) and ("Downloaded newer image" in status or "Image is up to date" in status):
                    pull_ok = True
            if not pull_ok:
                raise RuntimeError("pull finished without a success status")
            # Make sure to add correct tag if a digest was used since docker messes up the tag
            if not await self._ensure_tagged_local_image(client):
                raise RuntimeError(f"Image {self.source.docker}:{self.tag} missing after pull")

    async def _clear_remaining_tags(self) -> None:
        """Uninstall all other tags for this extension."""
        logger.info(f"Clearing remaining tags for extension {self.identifier}")
        to_clear: List[Extension] = cast(List[Extension], await self.from_settings(self.identifier))
        to_clear = [version for version in to_clear if version.source.tag != self.tag]
        await asyncio.gather(*(version.uninstall() for version in to_clear))

    async def install(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
        self, clear_remaining_tags: bool = True, atomic: bool = True
    ) -> AsyncGenerator[bytes, None]:
        logger.info(f"Installing extension {self.identifier}:{self.tag}")

        # First we should make sure no other tag is running
        sibling_image_id: Optional[str] = None
        sibling_id_unknown = False
        prior_settings: Optional[ExtensionSettings] = None
        try:
            existing = self.settings
            prior_settings = ExtensionSettings(
                identifier=existing.identifier,
                name=existing.name,
                docker=existing.docker,
                tag=existing.tag,
                permissions=existing.permissions,
                enabled=existing.enabled,
                user_permissions=existing.user_permissions,
            )
        except ExtensionNotFound:
            pass

        running_ext = await self._disable_running_extension()
        if running_ext and running_ext.unique_entry != self.unique_entry:
            try:
                async with DockerCtx() as client:
                    info = await self._inspect_or_none(client, f"{running_ext.source.docker}:{running_ext.tag}")
                image_id = info.get("Id") if isinstance(info, dict) else None
                sibling_image_id = image_id if isinstance(image_id, str) and image_id else None
                if not sibling_image_id:
                    sibling_id_unknown = True
            except Exception:
                sibling_id_unknown = True

        self._create_extension_settings()

        used_local_image = False
        try:
            self.lock(self.unique_entry)

            docker_auth = self._prepare_docker_auth()
            async for line in self._pull_docker_image(docker_auth):
                yield line
        except Exception as error:
            # In case of some external installs kraken shouldn't try to install it again so we
            # remove from settings. Keep a leftover docker:tag if it is not the running sibling's
            # image; otherwise roll back so we do not uninstall/delete the running image.
            local_ok = False
            if sibling_id_unknown:
                logger.warning(f"Could not inspect running image for {self.identifier}; refusing local-image fallback")
            else:
                try:
                    async with DockerCtx() as client:
                        local_ok = await self._ensure_tagged_local_image(client, sibling_image_id)
                except Exception as inspect_error:
                    logger.warning(
                        f"Could not verify image after pull of {self.identifier}:{self.tag}: {inspect_error}"
                    )
                    local_ok = False
            if local_ok:
                logger.warning(
                    f"Pull failed but image {self.identifier}:{self.tag} is already available locally: {error}"
                )
                used_local_image = True
            else:
                await self._rollback_failed_install(running_ext, prior_settings, atomic)
                raise ExtensionPullFailed(f"Failed to pull extension {self.identifier}:{self.tag}: {error}") from error
        finally:
            self.unlock(self.unique_entry)
            self.reset_start_attempt(self.unique_entry)

        logger.info(f"Extension {self.identifier}:{self.tag} installed")
        # Uninstall all other tags in case user wants to clear them
        if clear_remaining_tags and not used_local_image:
            await self._clear_remaining_tags()

    async def update(self, clear_remaining_tags: bool) -> AsyncGenerator[bytes, None]:
        async for data in self.install(clear_remaining_tags, atomic=True):
            yield data

    async def uninstall(self) -> None:
        old_settings = self.settings
        self._save_settings()

        try:
            await self.remove(old_settings.container_name())
        except ContainerNotFound:
            # If container was not found we must try to remove the image since it will be lost
            try:
                async with DockerCtx() as client:
                    await client.images.delete(old_settings.fullname(), force=True, noprune=False)
            except Exception:
                pass
        except Exception:
            # If its other exception we should just ignore since the main loop will take care
            pass

    async def start(self) -> None:
        logger.info(f"Starting extension {self.identifier}:{self.tag}")
        # Since some exts may keep restarting, we should keep track of attempts to start and avoid flooding
        # kraken main loop with start attempts
        self.mark_start_attempt(self.unique_entry)

        ext = self.settings
        config = ext.settings()

        img_name = ext.fullname()
        config["Image"] = img_name

        self._set_container_config_host_config(config)
        self._set_container_config_default_env_variables(config)

        try:
            async with DockerCtx() as client:
                # Checks if image exists locally, if not tries to pull it
                if not await self._ensure_tagged_local_image(client):
                    logger.info(f"Image not found locally, going to pull extension {self.identifier}:{self.tag}")
                    self.lock(self.unique_entry)
                    async for _ in self._pull_docker_image(self._prepare_docker_auth()):
                        pass

                container = await client.containers.create_or_replace(name=ext.container_name(), config=config)  # type: ignore
                await container.start()
                logger.info(f"Extension {self.identifier}:{self.tag} started")
                self.reset_start_attempt(self.unique_entry)
        except Exception as error:
            logger.warning(f"Failed to start extension {self.identifier}:{self.tag}: {error}")
            raise ExtensionPullFailed(f"Failed to start extension {self.identifier}:{self.tag}: {error}") from error
        finally:
            self.unlock(self.unique_entry)

    async def restart(self) -> None:
        # Just kill the container and let the orchestrator restart it
        await self.remove(self.settings.container_name(), False)
        self.reset_start_attempt(self.unique_entry)

    async def set_enabled(self, enabled: bool) -> None:
        ext = self.settings
        ext.enabled = enabled
        self._save_settings(ext)

    async def enable(self) -> None:
        await self.set_enabled(True)

    async def disable(self) -> None:
        try:
            await self.remove(self.settings.container_name(), False)
        except ContainerNotFound:
            pass
        await self.set_enabled(False)

    @classmethod
    async def from_settings(
        cls, identifier: Optional[str] = None, tag: Optional[str] = None
    ) -> List["Extension"] | "Extension":
        extensions: List[ExtensionSettings] | ExtensionSettings = cls._fetch_settings(identifier, tag)

        if isinstance(extensions, ExtensionSettings):
            return Extension(ExtensionSource.from_settings(extensions))

        return sorted(
            [Extension(ExtensionSource.from_settings(ext)) for ext in extensions],
            key=lambda ext: ext.source.name,
        )

    @staticmethod
    async def from_manifest(identifier: str, tag: Optional[str] = None) -> List["Extension"] | "Extension":
        manifest = ManifestManager.instance()

        entry = await manifest.fetch_extension(identifier)
        if not entry:
            raise ExtensionNotFound(f"Extension {identifier} not found")

        if tag is None:
            return [
                Extension(
                    ExtensionSource.from_repository_version(entry, v),
                    Extension.get_compatible_digest(v, identifier),
                )
                for _, v in entry.versions.items()
            ]

        version = await manifest.fetch_extension_version(identifier, tag)
        if not version:
            raise ExtensionNotFound(f"Extension {identifier}:{tag} not found")

        return Extension(
            ExtensionSource.from_repository_version(entry, version),
            Extension.get_compatible_digest(version, identifier),
        )

    @classmethod
    async def from_running(cls, identifier: str) -> "Extension":
        installed: List[Extension] = cast(List[Extension], await cls.from_settings(identifier))
        if not installed:
            raise ExtensionNotFound(f"Extension {identifier} not found")

        enabled = [ext for ext in installed if ext.source.enabled]
        if not enabled:
            raise ExtensionNotRunning(f"Extension {identifier} have no running versions")

        return enabled[0]

    @staticmethod
    async def from_latest(identifier: str, stable: bool = True) -> "Extension":
        manifest = ManifestManager.instance()

        entry = await manifest.fetch_extension(identifier)
        if not entry:
            raise ExtensionNotFound(f"Extension {identifier} not found")

        version = await manifest.fetch_latest_extension_version(identifier, stable)
        if not version:
            raise ExtensionNotFound(f"Extension {identifier} has no" + ("stable" if stable else "") + "versions")

        return Extension(
            ExtensionSource.from_repository_version(entry, version),
            Extension.get_compatible_digest(version, identifier),
        )

    @staticmethod
    def get_compatible_digest(version: ExtensionVersion, identifier: str, validate_size: bool = True) -> str:
        compatible_images = [image for image in version.images if image.compatible]

        if not compatible_images or compatible_images[0].digest is None:
            raise IncompatibleExtension(f"Extension {identifier}:{version.tag} has no compatible images")

        required_size = compatible_images[0].expanded_size
        if validate_size and not has_enough_disk_space(required_bytes=required_size):
            raise ExtensionInsufficientStorage(
                f"Extension {identifier}:{version.tag} requires at least {required_size / 2**20} MB free in storage."
            )

        return compatible_images[0].digest
