import asyncio
import base64
import json
import os
import tempfile
import time
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple, cast

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
        except ExtensionNotRunning:
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
        self._save_settings(new_extension)
        return new_extension

    def _prepare_docker_auth(self) -> Optional[str]:
        """Prepare Docker authentication string from source auth credentials."""
        if self.source.auth is None:
            return None
        docker_auth = f"{self.source.auth.username}:{self.source.auth.password}"
        return base64.b64encode(docker_auth.encode("utf-8")).decode("utf-8")

    async def _pull_docker_image(self, docker_auth: Optional[str]) -> AsyncGenerator[bytes, None]:
        """Pull Docker image and yield progress updates."""
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

    async def _clear_remaining_tags(self) -> None:
        """Uninstall all other tags for this extension."""
        logger.info(f"Clearing remaining tags for extension {self.identifier}")
        to_clear: List[Extension] = cast(List[Extension], await self.from_settings(self.identifier))
        to_clear = [version for version in to_clear if version.source.tag != self.tag]
        await asyncio.gather(*(version.uninstall() for version in to_clear))

    async def install(self, clear_remaining_tags: bool = True, atomic: bool = False) -> AsyncGenerator[bytes, None]:
        logger.info(f"Installing extension {self.identifier}:{self.tag}")

        # First we should make sure no other tag is running
        running_ext = await self._disable_running_extension()

        self._create_extension_settings()
        try:
            self.lock(self.unique_entry)

            docker_auth = self._prepare_docker_auth()
            async for line in self._pull_docker_image(docker_auth):
                yield line
        except Exception as error:
            # In case of some external installs kraken shouldn't try to install it again so we remove from settings
            if atomic:
                should_raise = False
                if not running_ext or self.unique_entry != running_ext.unique_entry:
                    should_raise = True
                    await self.uninstall()

                if running_ext:
                    await running_ext.enable()

                if should_raise:
                    raise ExtensionPullFailed(f"Failed to pull extension {self.identifier}:{self.tag}") from error
                # Reached only if the extensions are the same, the change is in permissions, not installation failure.
                return
        finally:
            self.unlock(self.unique_entry)
            self.reset_start_attempt(self.unique_entry)

        logger.info(f"Extension {self.identifier}:{self.tag} installed")
        # Uninstall all other tags in case user wants to clear them
        if clear_remaining_tags:
            await self._clear_remaining_tags()

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
                try:
                    await client.images.inspect(img_name)
                except Exception:
                    try:
                        logger.info(f"Image not found locally, going to pull extension {self.identifier}:{self.tag}")
                        self.lock(self.unique_entry)

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

    @staticmethod
    async def load_image_from_tar(tar_content: bytes) -> str:
        """
        Load a Docker image from tar file content and return the image name.

        Args:
            tar_content: The binary content of the tar file
        """
        async with DockerCtx() as client:
            # Use import_image with stream=True to get async iterator
            response = client.images.import_image(tar_content, stream=True)
            # Response contains stream data with image info
            # Extract image name from response
            async for line in response:
                if isinstance(line, dict) and "stream" in line:
                    stream = line["stream"]
                    if "Loaded image:" in stream or "Loaded image ID:" in stream:
                        # Extract image name from stream
                        parts = stream.strip().split()
                        if len(parts) >= 3:
                            image_name = parts[-1]
                            return image_name
                elif isinstance(line, dict) and "aux" in line:
                    aux = line["aux"]
                    if "Tag" in aux:
                        return aux["Tag"]
            # If we can't find it in stream, list images to find the newly loaded one
            images = await client.images.list()
            if images:
                # Return the most recently loaded image (last in list)
                return images[-1]["RepoTags"][0] if images[-1].get("RepoTags") else images[-1]["Id"]
            raise ExtensionPullFailed("Failed to load image from tar file")

    @staticmethod
    async def inspect_image_labels(image_name: str) -> Dict[str, Any]:
        """
        Inspect a Docker image and extract metadata from LABELs.
        Returns a dictionary with extracted metadata.
        """
        async with DockerCtx() as client:
            try:
                image_info = await client.images.inspect(image_name)
                labels = image_info.get("Config", {}).get("Labels", {})

                metadata: Dict[str, Any] = {}

                # Extract version
                if "version" in labels:
                    metadata["version"] = labels["version"]

                # Extract permissions (JSON string)
                if "permissions" in labels:
                    try:
                        permissions = json.loads(labels["permissions"])
                        metadata["permissions"] = json.dumps(permissions)
                    except json.JSONDecodeError:
                        metadata["permissions"] = labels["permissions"]

                # Extract authors (JSON array)
                if "authors" in labels:
                    try:
                        authors = json.loads(labels["authors"])
                        metadata["authors"] = authors
                    except json.JSONDecodeError:
                        metadata["authors"] = []

                # Extract company (JSON object)
                if "company" in labels:
                    try:
                        company = json.loads(labels["company"])
                        metadata["company"] = company
                    except json.JSONDecodeError:
                        metadata["company"] = {}

                # Extract type
                if "type" in labels:
                    metadata["type"] = labels["type"]

                # Extract readme URL
                if "readme" in labels:
                    metadata["readme"] = labels["readme"]

                # Extract links (JSON object)
                if "links" in labels:
                    try:
                        links = json.loads(labels["links"])
                        metadata["links"] = links
                    except json.JSONDecodeError:
                        metadata["links"] = {}

                # Extract requirements
                if "requirements" in labels:
                    metadata["requirements"] = labels["requirements"]

                # Extract image repo and tag for docker field
                repo_tags = image_info.get("RepoTags", [])
                if repo_tags:
                    repo_tag = repo_tags[0]
                    if ":" in repo_tag:
                        repo, tag = repo_tag.rsplit(":", 1)
                        metadata["docker"] = repo
                        metadata["tag"] = tag
                    else:
                        metadata["docker"] = repo_tag
                        metadata["tag"] = "latest"
                else:
                    # Fallback to image ID
                    image_id = image_info.get("Id", "")
                    metadata["docker"] = image_id[:12] if image_id else "unknown"
                    metadata["tag"] = "latest"

                # Try to extract name from company or use a default
                DEFAULT_EXTENSION_NAME = "Unknown Extension"
                if "name" not in metadata:
                    if "company" in metadata and isinstance(metadata["company"], dict):
                        metadata["name"] = metadata["company"].get("name", DEFAULT_EXTENSION_NAME)
                    else:
                        metadata["name"] = metadata.get("docker", DEFAULT_EXTENSION_NAME).split("/")[-1]

                return metadata
            except Exception as error:
                raise ExtensionPullFailed(f"Failed to inspect image {image_name}") from error

    @classmethod
    async def create_temporary_extension(cls, image_name: str, metadata: Dict[str, Any]) -> "Extension":
        """
        Create a temporary extension with empty identifier to track the uploaded image.
        """
        # Generate a unique tag for the temporary extension
        import uuid

        temp_tag = f"temp-{uuid.uuid4().hex[:8]}"

        # Extract or set defaults
        DEFAULT_EXTENSION_NAME = "Unknown Extension"
        name = metadata.get("name", DEFAULT_EXTENSION_NAME)
        docker = metadata.get("docker", image_name.split(":")[0] if ":" in image_name else image_name)
        permissions = metadata.get("permissions", json.dumps({}))

        # Create temporary extension with empty identifier
        temp_source = ExtensionSource(
            identifier="",  # Empty identifier marks it as temporary
            tag=temp_tag,
            name=name,
            docker=docker,
            enabled=False,
            permissions=permissions,
            user_permissions="",
        )

        extension = Extension(temp_source)

        # Save temporary extension settings
        # Use temp_tag for the settings entry, but docker points to actual loaded image
        temp_settings = ExtensionSettings(
            identifier="",
            name=name,
            docker=docker,  # This is the actual loaded image repo
            tag=temp_tag,  # Use temp_tag to identify this temporary entry
            permissions=permissions,
            enabled=False,
            user_permissions="",
        )
        extension._save_settings(temp_settings)

        # Tag the loaded image with the temp_tag for reference
        async with DockerCtx() as client:
            try:
                await client.images.tag(image_name, f"{docker}:{temp_tag}")
            except Exception as error:
                logger.warning(f"Failed to tag image with temp tag: {error}")

        return extension

    @classmethod
    async def finalize_temporary_extension(
        cls, temp_extension: "Extension", identifier: str, source: ExtensionSource
    ) -> "Extension":
        """
        Finalize a temporary extension by assigning a valid identifier and updating settings.
        """
        old_settings = temp_extension.settings

        # Create new extension with valid identifier
        new_extension = Extension(source)

        # Remove old temporary extension
        temp_extension._save_settings()

        # Save new extension
        new_settings = ExtensionSettings(
            identifier=identifier,
            name=source.name,
            docker=source.docker,
            tag=source.tag,
            permissions=source.permissions,
            enabled=source.enabled,
            user_permissions=source.user_permissions,
        )
        new_extension._save_settings(new_settings)

        # Tag the image with the new identifier if needed
        if old_settings.docker != source.docker or old_settings.tag != source.tag:
            async with DockerCtx() as client:
                try:
                    await client.images.tag(
                        f"{old_settings.docker}:{old_settings.tag}", f"{source.docker}:{source.tag}"
                    )
                except Exception as error:
                    logger.warning(f"Failed to tag image: {error}")

        return new_extension

    @classmethod
    async def cleanup_temporary_extensions(cls) -> None:
        """
        Clean up temporary extensions (those with empty identifiers) and their images.
        """
        extensions: List[ExtensionSettings] = cls._fetch_settings()
        temp_extensions = [ext for ext in extensions if not ext.identifier or ext.identifier == ""]

        for ext in temp_extensions:
            try:
                extension = Extension(ExtensionSource.from_settings(ext))
                await extension.uninstall()
                logger.info(f"Cleaned up temporary extension {ext.docker}:{ext.tag}")
            except Exception as error:
                logger.warning(f"Failed to cleanup temporary extension {ext.docker}:{ext.tag}: {error}")
