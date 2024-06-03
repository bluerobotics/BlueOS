import asyncio
import traceback
from typing import List

from commonwealth.settings.manager import Manager
from loguru import logger

from config import SERVICE_NAME
from extension.exceptions import IncompatibleExtension
from extension.extension import Extension
from extension.models import ExtensionSource
from harbor import ContainerManager
from manifest import ManifestManager
from settings import ExtensionSettings, SettingsV2


class Kraken:
    def __init__(self) -> None:
        self._manager: Manager = Manager(SERVICE_NAME, SettingsV2)
        self._settings = self._manager.settings
        self.is_running = True
        self.manifest = ManifestManager.instance()

    async def init_dead_extensions(self) -> None:
        # This can fail if docker daemon is not running
        try:
            containers = await ContainerManager.get_running_containers()
        except Exception as e:
            logger.error(f"Unable to list docker containers: {e}")
            return

        extensions: List[ExtensionSettings] = Extension._fetch_settings()

        for extension in extensions:
            # If we found the identifier in the locked entries we skip the extension since its being pulled
            if not extension.enabled or (extension.identifier + extension.tag) in Extension.locked_entries:
                continue

            extension_name = extension.container_name()
            if not any(container.name[1:] == extension_name for container in containers):
                try:
                    version = await self.manifest.fetch_extension_version(extension.identifier, extension.tag)
                    digest = None
                    if version:
                        digest = Extension.get_compatible_digest(version, extension.identifier)
                    else:
                        logger.warning(
                            f"Dead extension {extension.identifier}:{extension.tag} is external and likely requires authentication"
                        )

                    await (Extension(ExtensionSource.from_settings(extension), digest)).start()
                except IncompatibleExtension:
                    logger.warning(f"Dead extension {extension.identifier}:{extension.tag} is not compatible anymore")
                except Exception as e:
                    traceback.print_exc()
                    logger.warning(f"Dead extension {extension.identifier}:{extension.tag} could not be started: {e}")

    async def kill_invalid_extensions(self) -> None:
        extensions: List[ExtensionSettings] = Extension._fetch_settings()

        for extension in extensions:
            if not extension.is_valid():
                try:
                    await (Extension(ExtensionSource.from_settings(extension))).uninstall()
                except Exception as e:
                    logger.warning(
                        f"Invalid extension {extension.identifier}:{extension.tag} could not be uninstalled: {e}"
                    )

    async def kill_dangling_containers(self) -> None:
        # This can fail if docker daemon is not running
        try:
            containers = await ContainerManager.get_running_containers()
        except Exception as e:
            logger.error(f"Unable to list docker containers: {e}")
            return

        extensions: List[ExtensionSettings] = Extension._fetch_settings()

        for container in containers:
            container_name = container.name[1:]
            # In case some extension is being removed the container name will be in locked entries
            if (
                container_name not in Extension.locked_entries
                and container_name.startswith("extension-")
                and container_name not in [ext.container_name() for ext in extensions]
            ):
                try:
                    await Extension.remove(container_name)
                except Exception as e:
                    logger.warning(f"Dangling container {container_name} could not be removed: {e}")

    async def poll(self) -> None:
        await self.init_dead_extensions()
        await self.kill_invalid_extensions()
        await self.kill_dangling_containers()

    async def start(self) -> None:
        while self.is_running:
            await asyncio.sleep(5)
            await self.poll()

    async def stop(self) -> None:
        self.is_running = False
