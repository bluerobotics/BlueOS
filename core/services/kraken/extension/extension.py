import asyncio
import json
from typing import AsyncGenerator, List, Optional

from commonwealth.settings.manager import Manager
from config import SERVICE_NAME
from manifest import Manifest
from manifest.models import Image
from settings import Extension as ExtensionSettings, SettingsV1
from app.docker.docker import DockerCtx
from kraken.exceptions import ExtensionContainerNotFound, ExtensionNotFound, ExtensionPullFailed


class Extension:
    """
    Extension class to manage extensions.
    """

    def __init__(
        self,
        identifier: str,
        tag: str,
        image: Optional[Image] = None,
        manager: Optional[Manager] = None,
    ) -> None:
        """
        Initialize the extension.

        Args:
            identifier (str): Identifier of the extension.
            tag (str): Tag of the extension.
            image (Optional[Image]): If provided will use this image to install and manage the extension.
            manager (Optional[Manager]): Settings manager instance to use, if not provided will create a new one.
        """

        # Load settings
        self.manager = manager if manager else Manager(SERVICE_NAME, SettingsV1)
        self.settings = self.manager.settings
        # Save identifiers
        self.identifier = identifier
        self.tag = tag
        self.image = image
        # Get manifest
        self.manifest = Manifest.instance()


    def fetch_settings(self, identifier: str, tag: Optional[str] = None) -> List[ExtensionSettings] | ExtensionSettings:
        """
        Fetch settings for an extension.

        Args:
            identifier (str): Identifier of the extension.
            tag (Optional[str]): Tag of the extension, if not provided will return all tags.

        Returns:
            List[ExtensionSettings] | ExtensionSettings: Settings for the extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
        """

        extensions: List[ExtensionSettings] = [
            extension
            for extension in self.settings.extensions
            if extension.identifier == identifier and (not tag or extension.tag == tag)
        ]
        if tag:
            if extensions:
                return extensions[0]
            else:
                raise ExtensionNotFound(f"Extension {identifier}:{tag} not found in settings")
        return extensions if extensions else []


    def save_settings(self, extension: Optional[ExtensionSettings] = None) -> None:
        """
        Save settings.

        Args:
            extension (Optional[ExtensionSettings]): Extension to save, if not provided will remove current extension.
        """

        self.settings.extensions = [
            other
            for other in self.settings.extensions
            if not (other.identifier == self.identifier and other.tag == self.tag)
        ]
        if extension:
            self.settings.extensions.append(extension)
        self.manager.save()


    async def remove(self, delete: bool = True) -> None:
        """
        Remove current extension.

        Args:
            delete (bool): Delete the image associated with the extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
            ExtensionContainerNotFound: If the container is not found.
        """

        ext = self.fetch_settings(self.identifier, self.tag)

        container_name = str(ext.container_name())

        async with DockerCtx() as client:
            container = await client.containers.list(filters={"name": {container_name: True}})

            if not container:
                raise ExtensionContainerNotFound(f"Container {container_name} not found for extension {self.identifier}:{self.tag}")

            image = container[0]["Image"]
            await self.kill(container_name)
            await container[0].delete()

            if delete:
                client.images.delete(image, force=True, noprune=False)


    async def install(self, clear_remaining_tags: bool = True) -> AsyncGenerator[bytes, None]:
        """
        Install current extension.

        Args:
            clear_remaining_tags (bool): Delete all other tags with this identifier after install.

        Raises:
            ExtensionNotFound: If the extension is not found in manifest.
            ExtensionPullFailed: If the extension fails to pull.
        """

        entry = await self.manifest.get_extension(self.identifier)
        tag = entry.versions.get(self.tag, None)

        if not entry or not tag:
            raise ExtensionNotFound(f"Extension {self.identifier}:{self.tag} not found in manifest")

        ext = ExtensionSettings(
            identifier=self.identifier,
            tag=self.tag,
            name=entry.name,
            docker=entry.docker,
            permissions=tag.permissions,
            enabled=True,
            # TODO - Right now this data was coming empty from frontend, should be moved to manifest
            user_permissions="",
        )
        # Save in settings first, if the image fails to install it will try to fetch after in main kraken check loop
        self.settings.extensions.append(ext)
        self.manager.save()

        # Get the extension
        try:
            tag = f"{entry.docker}:{self.tag}" + (f":{self.image.digest}" if self.image and self.image.digest else "")

            async with DockerCtx() as client:
                async for line in client.images.pull(tag, repo=entry.docker, tag=self.tag, stream=True):
                    yield json.dumps(line).encode("utf-8")
        except Exception as error:
            raise ExtensionPullFailed(f"Failed to pull extension {self.identifier}:{self.tag}") from error

        # Clear older ones
        if clear_remaining_tags:
            to_clear = [
                Extension(self.identifier, version.tag, manager=self.manager)
                for version in self.fetch_settings(self.identifier)
                if version.tag != self.tag
            ]
            await asyncio.gather(*(version.uninstall() for version in to_clear))


    async def update(self) -> None:
        """
        Update current extension.

        Raises:
            ExtensionNotFound: If the extension is not found in manifest.
            ExtensionPullFailed: If the extension fails to pull.
        """

        return await self.install(True)


    async def uninstall(self) -> None:
        """
        Uninstall current extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
            ExtensionContainerNotFound: If the container is not found.
        """

        await self.remove()
        # Remove self from settings
        self.save_settings()


    async def start(self) -> None:
        """
        Start current extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
        """

        ext = self.fetch_settings(self.identifier, self.tag)
        config = ext.settings()

        img_name = ext.fullname()
        config["Image"] = img_name

        async with DockerCtx() as client:
            # Checks if image exists locally, if not tries to pull it
            try:
                await client.images.inspect(img_name)
            except Exception:
                try:
                    await client.images.pull(img_name)
                except Exception as error:
                    raise ExtensionPullFailed(f"Failed to pull extension {self.identifier}:{self.tag}") from error

            container = await client.containers.create_or_replace(
                name=ext.container_name(), config=config
            )
            await container.start()


    async def restart(self) -> None:
        """
        Restart current extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
            ExtensionContainerNotFound: If the container is not found.
        """

        await self.remove(False)


    async def enable(self) -> None:
        """
        Enable current extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
        """

        ext = self.fetch_settings(self.identifier, self.tag)
        ext.enabled = True
        self.save_settings(ext)


    async def disable(self) -> None:
        """
        Disable current extension.

        Raises:
            ExtensionNotFound: If the extension is not found in settings.
            ExtensionContainerNotFound: If the container is not found.
        """

        ext = self.fetch_settings(self.identifier, self.tag)

        await self.remove(False)

        ext.enabled = False
        self.save_settings(ext)


    @staticmethod
    async def from_compatible_image(identifier: str, tag: str) -> Optional["Extension"]:
        """
        Returns an extension from a compatible image if found.

        Args:
            identifier (str): Identifier of the extension.
            tag (str): Tag of the extension.

        Returns:
            Optional[Extension]: Extension if found otherwise None.
        """

        manifest = Manifest.instance()

        version = await manifest.get_extension_version(identifier, tag)
        if not version:
            return None

        compatible_images = [image for image in version.images if image.compatible]

        return Extension(identifier, tag, image=compatible_images[0]) if compatible_images else None


    @staticmethod
    async def latest_tag(identifier: str) -> Optional[str]:
        """
        Returns the latest tag for an extension.

        Args:
            identifier (str): Identifier of the extension.

        Returns:
            str: Latest tag of the extension.
        """

        manifest = Manifest.instance()
        extension = await manifest.get_extension(identifier)
        versions = sorted(extension.versions.keys())

        if "latest" in versions:
            return "latest"

        return versions.pop() if extension and versions else None


    @staticmethod
    async def latest_installed_tag(identifier: str) -> Optional[str]:
        """
        Returns the latest tag for an extension.

        Args:
            identifier (str): Identifier of the extension.

        Returns:
            str: Latest tag of the extension.
        """

        manifest = Manifest.instance()
        extension = await manifest.get_extension(identifier)
        versions = sorted(extension.versions.keys())

        if "latest" in versions:
            return "latest"

        return versions.pop() if extension and versions else None
