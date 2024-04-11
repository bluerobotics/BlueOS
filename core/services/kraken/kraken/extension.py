import json
import asyncio
from typing import AsyncGenerator, List, Optional
# Package
from config import SERVICE_NAME
from manifest import Manifest
from manifest.models import Image
from kraken.docker import DockerCtx
# Extra
from commonwealth.settings.manager import Manager
from settings import Extension as ExtensionSettings, SettingsV1

class ExtensionNotFound(Exception):
    pass

class ExtensionPullFailed(Exception):
    pass

class ExtensionContainerNotFound(Exception):
    pass

class Extension:
    def __init__(
        self,
        identifier: str,
        tag: str,
        image: Optional[Image] = None,
        manager: Optional[Manager] = None,
    ) -> None:
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
        self.settings.extensions = [
            other
            for other in self.settings.extensions
            if not (other.identifier == self.identifier and other.tag == self.tag)
        ]
        if extension:
            self.settings.extensions.append(extension)
        self.manager.save()


    async def remove(self, delete: bool = True) -> None:
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
        return await self.install(True)


    async def uninstall(self) -> None:
        await self.remove()
        # Remove self from settings
        self.save_settings()


    async def restart(self) -> None:
        await self.remove(False)


    async def enable(self) -> None:
        ext = self.fetch_settings(self.identifier, self.tag)
        ext.enabled = True
        self.save_settings(ext)


    async def disable(self) -> None:
        ext = self.fetch_settings(self.identifier, self.tag)

        await self.remove(False)

        ext.enabled = False
        self.save_settings(ext)


    @staticmethod
    async def from_compatible_image(identifier: str, tag: str) -> Optional["Extension"]:
        manifest = Manifest.instance()

        version = await manifest.get_extension_version(identifier, tag)
        if not version:
            return None

        compatible_images = [image for image in version.images if image.compatible]

        return Extension(identifier, tag, image=compatible_images[0]) if compatible_images else None
