import asyncio
import traceback
from typing import Any, List

import aiohttp
from commonwealth.settings.manager import Manager
from loguru import logger

from config import DEFAULT_EXTENSIONS, SERVICE_NAME
from extension.exceptions import IncompatibleExtension
from extension.extension import Extension
from extension.models import ExtensionSource
from harbor import ContainerManager
from jobs import JobsManager
from jobs.models import Job, JobMethod
from manifest import ManifestManager
from manifest.exceptions import ManifestBackendOffline
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
            if (
                not extension.enabled
                or f"{extension.identifier}{extension.tag}" in Extension.locked_entries
                or extension.container_name() in Extension.locked_entries
            ):
                continue

            extension_name = extension.container_name()
            if not any(container.name[1:] == extension_name for container in containers):
                digest = None
                try:
                    version = await self.manifest.fetch_extension_version(extension.identifier, extension.tag)
                    if version:
                        digest = Extension.get_compatible_digest(version, extension.identifier, False)
                    else:
                        logger.warning(
                            f"Dead extension {extension.identifier}:{extension.tag} is external and likely requires authentication"
                        )
                except IncompatibleExtension:
                    logger.warning(f"Dead extension {extension.identifier}:{extension.tag} is not compatible anymore")
                except ManifestBackendOffline:
                    logger.warning(
                        f"Could not fetch manifest since the backend is offline, will try to start {extension.identifier}:{extension.tag} anyway"
                    )
                except Exception:
                    logger.warning(
                        f"Unable to fetch manifest, will try to start {extension.identifier}:{extension.tag} anyway. Error: {traceback.format_exc()}"
                    )

                try:
                    await (Extension(ExtensionSource.from_settings(extension), digest)).start()
                except Exception:
                    logger.warning(
                        f"Dead extension {extension.identifier}:{extension.tag} could not be started: {traceback.format_exc()}"
                    )

    async def fetch_default_extension_data(self, url: str) -> Any:
        async with aiohttp.ClientSession() as session:
            headers = {"Accept": "application/json"}
            async with session.get(url, headers=headers) as resp:
                resp.raise_for_status()
                return await resp.json()

    def is_install_default_ext_job_created(self, identifier: str) -> bool:
        try:
            JobsManager.get_by_identifier(identifier)
        except Exception:
            return False
        return True

    async def setup_default_extensions(self) -> None:
        extensions: List[ExtensionSettings] = Extension._fetch_settings()
        for ext in [
            ext
            for ext in DEFAULT_EXTENSIONS
            if not any(ext["identifier"] == extension.identifier for extension in extensions)
        ]:
            job_id = f'__default_install_{ext["identifier"]}'
            if not self.is_install_default_ext_job_created(job_id):
                data = await self.fetch_default_extension_data(ext["url"])
                job = Job(
                    id=job_id,
                    route="v2.0/extension",
                    method=JobMethod.POST,
                    body=data,
                    retries=1,
                )
                JobsManager.add(job)
                logger.info(f"Created job to install default extension {ext['identifier']}")

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
        await self.setup_default_extensions()
        await self.kill_invalid_extensions()
        await self.kill_dangling_containers()

    async def start(self) -> None:
        while self.is_running:
            await asyncio.sleep(5)
            await self.poll()

    async def stop(self) -> None:
        self.is_running = False
