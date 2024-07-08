import asyncio
import base64
import json
from typing import AsyncGenerator, Dict, List, Literal, Optional, cast

from commonwealth.settings.manager import Manager
from loguru import logger

from config import SERVICE_NAME
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
    def settings(self) -> ExtensionSettings:
        return cast(ExtensionSettings, self._fetch_settings(self.identifier, self.tag))

    @classmethod
    def lock(cls, key: str) -> None:
        cls.locked_entries[key] = True

    @classmethod
    def unlock(cls, key: str) -> None:
        cls.locked_entries.pop(key, None)

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

    async def install(self, clear_remaining_tags: bool = True, atomic: bool = False) -> AsyncGenerator[bytes, None]:
        logger.info(f"Installing extension {self.identifier}:{self.tag}")

        # First we should make sure no other tag is running
        running_ext = None
        try:
            running_ext = await self.from_running(self.identifier)
            if running_ext:
                await running_ext.disable()
        except ExtensionNotRunning:
            pass

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
        self._save_settings(new_extension)

        try:
            self.lock(self.identifier + self.tag)

            docker_auth: Optional[str] = None
            if self.source.auth is not None:
                docker_auth = f"{self.source.auth.username}:{self.source.auth.password}"
                docker_auth = base64.b64encode(docker_auth.encode("utf-8")).decode("utf-8")

            tag = f"{self.source.docker}:{self.tag}" + (f"@{self.digest}" if self.digest else "")
            async with DockerCtx() as client:
                async for line in client.images.pull(
                    tag, repo=self.source.docker, tag=self.tag, auth=docker_auth, stream=True
                ):
                    # TODO - Plug Error detection from docker image here
                    yield json.dumps(line).encode("utf-8")
                # Make sure to add correct tag if a digest was used since docker messes up the tag
                if self.digest:
                    await client.images.tag(tag, f"{self.source.docker}:{self.tag}")
        except Exception as error:
            # In case of some external installs kraken shouldn't try to install it again so we remove from settings
            if atomic:
                await self.uninstall()
                if running_ext:
                    await running_ext.enable()
            raise ExtensionPullFailed(f"Failed to pull extension {self.identifier}:{self.tag}") from error
        finally:
            self.unlock(self.identifier + self.tag)

        logger.info(f"Extension {self.identifier}:{self.tag} installed")
        # Uninstall all other tags in case user wants to clear them
        if clear_remaining_tags:
            logger.info(f"Clearing remaining tags for extension {self.identifier}")
            to_clear: List[Extension] = cast(List[Extension], await self.from_settings(self.identifier))
            to_clear = [version for version in to_clear if version.source.tag != self.tag]
            await asyncio.gather(*(version.uninstall() for version in to_clear))

    async def update(self, clear_remaining_tags: bool) -> AsyncGenerator[bytes, None]:
        async for data in self.install(clear_remaining_tags):
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

        ext = self.settings
        config = ext.settings()

        img_name = ext.fullname()
        config["Image"] = img_name

        if "HostConfig" not in config:
            config["HostConfig"] = {}
        if "LogConfig" not in config["HostConfig"]:
            config["HostConfig"]["LogConfig"] = {}
        config["HostConfig"]["LogConfig"] = {"Type": "json-file", "Config": {"max-size": "20m", "max-file": "3"}}

        try:
            async with DockerCtx() as client:
                # Checks if image exists locally, if not tries to pull it
                try:
                    await client.images.inspect(img_name)
                except Exception:
                    try:
                        logger.info(f"Image not found locally, going to pull extension {self.identifier}:{self.tag}")
                        self.lock(self.identifier + self.tag)

                        tag = img_name + (f"@{self.digest}" if self.digest else "")
                        await client.images.pull(tag, repo=self.source.docker, tag=self.tag)
                        # Make sure to add correct tag if a digest was used since docker messes up the tag
                        if self.digest:
                            await client.images.tag(tag, img_name)
                    except Exception as error:
                        raise ExtensionPullFailed(f"Failed to pull extension {self.identifier}:{self.tag}") from error

                container = await client.containers.create_or_replace(name=ext.container_name(), config=config)  # type: ignore
                await container.start()
                logger.info(f"Extension {self.identifier}:{self.tag} started")
        except Exception as error:
            logger.warning(f"Failed to start extension {self.identifier}:{self.tag}: {error}")
            raise ExtensionPullFailed(f"Failed to start extension {self.identifier}:{self.tag}: {error}") from error
        finally:
            self.unlock(self.identifier + self.tag)

    async def restart(self) -> None:
        # Just kill the container and let the orchestrator restart it
        await self.remove(self.settings.container_name(), False)

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
