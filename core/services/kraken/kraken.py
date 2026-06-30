import asyncio
import time
import traceback
from typing import Any, List

import aiohttp
from commonwealth.settings.manager import PydanticManager
from config import DEFAULT_EXTENSIONS, SERVICE_NAME
from extension.exceptions import IncompatibleExtension
from extension.extension import Extension
from extension.models import ExtensionSource
from extension_logs import ExtensionLogPublisher
from harbor import ContainerManager
from jobs import JobsManager
from jobs.models import Job, JobMethod
from loguru import logger
from manifest import ManifestManager
from manifest.exceptions import ManifestBackendOffline
from settings import ExtensionSettings, SettingsV2


class Kraken:
    def __init__(self) -> None:
        self._manager: PydanticManager = PydanticManager(SERVICE_NAME, SettingsV2)
        self._settings = self._manager.settings
        self.is_running = True
        self.manifest = ManifestManager.instance()
        self.extension_log_publisher = ExtensionLogPublisher()

    def _extension_start_try_valid(self, extension: ExtensionSettings) -> bool:
        unique_entry = f"{extension.identifier}{extension.tag}"

        attempts, last_attempt = Extension.start_attempts.get(unique_entry, (0, 0))
        maximum_delay = 600
        minimum_delay = 10
        required_delay = (
            max(minimum_delay * (attempts != 0) + 2**attempts, maximum_delay) if attempts < 8 else maximum_delay
        )

        now = int(time.monotonic())

        # If we found the identifier in the locked entries we skip the extension since its being pulled
        return (
            extension.enabled
            and unique_entry not in Extension.locked_entries
            and extension.container_name() not in Extension.locked_entries
        ) and (unique_entry not in Extension.start_attempts or (now - last_attempt > required_delay))

    async def init_dead_extensions(self) -> None:
        # This can fail if docker daemon is not running
        try:
            containers = await ContainerManager.get_running_containers()
        except Exception as e:
            logger.error(f"Unable to list docker containers: {e}")
            return

        extensions: List[ExtensionSettings] = Extension._fetch_settings()

        for extension in extensions:
            if not self._extension_start_try_valid(extension):
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

    async def cleanup_temporary_extensions(self) -> None:
        """
        Clean up expired temporary extensions (those with empty identifiers and stale keep-alives).
        This helps prevent accumulation of abandoned temporary extensions from failed uploads.
        """
        await Extension.cleanup_temporary_extensions()

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

    async def start_starter_task(self) -> None:
        while self.is_running:
            await self.init_dead_extensions()

            await asyncio.sleep(5)

    async def start_cleaner_task(self) -> None:
        while self.is_running:
            await self.setup_default_extensions()
            await self.kill_invalid_extensions()
            await self.kill_dangling_containers()
            await self.cleanup_temporary_extensions()

            await asyncio.sleep(60)

    async def start_extension_logs_task(self) -> None:
        while self.is_running:
            try:
                await self.extension_log_publisher.sync_with_running_extensions()
            except Exception as error:
                logger.debug(f"Failed to sync extension log streams: {error}")
            await asyncio.sleep(2)

    async def stop(self) -> None:
        self.is_running = False
        await self.extension_log_publisher.shutdown()
