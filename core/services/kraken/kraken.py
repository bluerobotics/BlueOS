import asyncio
import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, cast

import aiodocker
import aiohttp
import psutil
from aiodocker.docker import DockerContainer
from commonwealth.settings.manager import Manager
from commonwealth.utils.apis import StackedHTTPException
from fastapi import status
from loguru import logger

from exceptions import ContainerDoesNotExist, ExtensionNotFound
from settings import Extension, SettingsV1

REPO_URL = "https://bluerobotics.github.io/BlueOS-Extensions-Repository/manifest.json"
SERVICE_NAME = "Kraken"


class Kraken:
    def __init__(self) -> None:
        self.load_settings()
        self.running_containers: List[DockerContainer] = []
        self.should_run = True
        self.deleting_in_progress = False
        self._client: Optional[aiodocker.Docker] = None
        self.manifest_cache: List[Dict[str, Any]] = []

    @property
    def client(self) -> aiodocker.Docker:
        if self._client is None:
            self._client = aiodocker.Docker()
        return self._client

    async def run(self) -> None:
        while self.should_run:
            await asyncio.sleep(5)
            if self.deleting_in_progress:
                continue

            running_containers: List[DockerContainer] = await self.client.containers.list(  # type: ignore
                filter='{"status": ["running"]}'
            )
            self.running_containers = running_containers

            for extension in self.settings.extensions:
                await self.check(extension)

    async def start_extension(self, extension: Extension) -> None:
        logger.info(f"Going to start {extension}.")
        config = extension.settings()
        config["Image"] = extension.fullname()
        logger.info(f"Starting extension '{extension.fullname()}'.")
        try:
            await self.client.images.pull(extension.fullname())
        except aiodocker.exceptions.DockerError:  # raised if we are offline
            logger.info("Unable to pull a new image, attempting to continue with a local one.")
        container = await self.client.containers.create_or_replace(name=extension.container_name(), config=config)  # type: ignore
        await container.start()

    async def check(self, extension: Extension) -> None:
        if not extension.enabled:
            return
        if not extension.is_valid():
            logger.warning(f"{extension.identifier} is invalid, removing it.")
            try:
                await self.uninstall_extension(extension)
            except ContainerDoesNotExist:
                logger.warning(f"Container for extension {extension.identifier} was not up?")
            return

        extension_name = extension.container_name()
        # Names is a list of of lists like ["[['/blueos-core'], ..."]
        # We assume which container has only one tag, and remove '/' using the [1:] slicing
        if not extension.enabled:
            return
        if not any(container["Names"][0][1:] == extension_name for container in self.running_containers):
            await self.start_extension(extension)

    def load_settings(self) -> None:
        self.manager = Manager(SERVICE_NAME, SettingsV1)
        self.settings = self.manager.settings

    async def fetch_manifest(self) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.get(REPO_URL) as resp:
                if resp.status != 200:
                    print(f"Error status {resp.status}")
                    raise RuntimeError(f"Could not fetch manifest file: response status : {resp.status}")
                self.manifest_cache = await resp.json()
                return await resp.json(content_type=None)

    async def get_configured_extensions(self) -> List[Extension]:
        return cast(List[Extension], self.settings.extensions)

    async def install_extension(self, extension: Any) -> AsyncGenerator[bytes, None]:
        try:
            # Remove older entry if it exists
            installed_extension = await self.extension_from_identifier(extension.identifier)
            if installed_extension is not None:
                await self.uninstall_extension(installed_extension)
        except Exception as e:
            # this will fail if the container is not installed, we don't mind it
            logger.info(e)
        new_extension = Extension(
            identifier=extension.identifier,
            name=extension.name,
            docker=extension.docker,
            tag=extension.tag,
            permissions=extension.permissions,
            enabled=extension.enabled,
            user_permissions=extension.user_permissions,
        )
        self.settings.extensions.append(new_extension)
        self.manager.save()
        try:
            async for line in self.client.images.pull(
                f"{extension.docker}:{extension.tag}", repo=extension.docker, tag=extension.tag, stream=True
            ):
                yield json.dumps(line).encode("utf-8")
        except Exception as error:
            raise StackedHTTPException(status_code=status.HTTP_404_NOT_FOUND, error=error) from error

    async def extension_from_identifier(self, identifier: str) -> Optional[Extension]:
        extensions: List[Extension] = [
            extension for extension in self.settings.extensions if extension.identifier == identifier
        ]
        if extensions:
            return extensions[0]
        return None

    async def container_from_identifier(self, extension_identifier: str) -> str:
        extension = await self.extension_from_identifier(extension_identifier)
        if not extension:
            raise RuntimeError(f"Could not find container for {extension_identifier}, is it running?")
        return str(extension.container_name())

    async def kill(self, container_name: str) -> None:
        logger.info(f"Killing {container_name}")
        containers = await self.client.containers.list(filters={"name": {container_name: True}})  # type: ignore
        for container in containers:
            await container.kill()
            await container.wait()

    async def remove(self, extension_identifier: str, delete: bool = True) -> None:
        self.deleting_in_progress = True
        logger.info(f"Removing extension {extension_identifier}")
        container_name = await self.container_from_identifier(extension_identifier)
        container = await self.client.containers.list(filters={"name": {container_name: True}})  # type: ignore
        if not container:
            self.deleting_in_progress = False
            raise ContainerDoesNotExist(f"Unable remove {container_name}. Container not found.")
        image = container[0]["Image"]
        await self.kill(container_name)
        await container[0].delete()
        if delete:
            logger.info(f"Removing {image}")
            await self.client.images.delete(image, force=False, noprune=False)
        self.deleting_in_progress = False

    async def update_extension_to_version(self, identifier: str, version: str) -> AsyncGenerator[bytes, None]:
        extension = await self.extension_from_identifier(identifier)
        if not extension:
            raise RuntimeError(f"Extension with identifier {identifier} not found!")
        # TODO: plug dependency-checking in here
        version_manifests = [entry for entry in self.manifest_cache if entry["identifier"] == identifier]
        if not version_manifests:
            raise RuntimeError(f"identifier not found in manifest: {identifier}")
        manifest = version_manifests[0]
        if version not in manifest["versions"]:
            raise RuntimeError(f"version not found in manifest: {version}")
        await self.uninstall_extension_from_identifier(identifier)
        version_data = manifest["versions"][version]

        new_extension = Extension(
            identifier=identifier,
            name=extension.name,
            docker=extension.docker,
            tag=version_data["tag"],
            permissions=json.dumps(version_data["permissions"]),
            enabled=True,
            # TODO: handle user permissions on updates
            user_permissions="",
        )

        # Remove older entry if it exists
        self.settings.extensions = [
            old_extension
            for old_extension in self.settings.extensions
            if old_extension.identifier != extension.identifier
        ]
        self.settings.extensions.append(new_extension)
        self.manager.save()

        try:
            await self.remove(extension.identifier, False)
        except Exception as e:
            # this will fail if the container is not installed, we don't mind it
            logger.info(e)

        try:
            async for line in self.client.images.pull(
                f"{extension.docker}:{extension.tag}", repo=extension.docker, tag=extension.tag, stream=True
            ):
                yield json.dumps(line).encode("utf-8")
        except Exception as error:
            raise StackedHTTPException(status_code=status.HTTP_404_NOT_FOUND, error=error) from error

    async def uninstall_extension_from_identifier(self, identifier: str) -> None:
        extension = await self.extension_from_identifier(identifier)
        if not extension:
            raise ExtensionNotFound(f"Could not find extension with identifier '{identifier}'.")
        await self.uninstall_extension(extension)

    async def uninstall_extension(self, extension: Extension) -> None:
        try:
            await self.remove(extension.identifier)
        except Exception as e:
            logger.warning(f"Unable to remove container {e}")

        # TODO: remove this  section sometime in 2023
        # This is here to cope with a change between betas.
        # we had name mistakenly taking the docker name
        logger.warning("Attempting to find container with old beta nomenclature.")
        regex = re.compile("[^a-zA-Z0-9]")
        container_name = "extension-" + regex.sub("", f"{extension.name}{extension.tag}")
        container = await self.client.containers.list(filters={"name": {container_name: True}})  # type: ignore
        if container:
            await self.kill(container_name)
            await container[0].delete()
        # end of section to delete

        self.settings.extensions = [
            old_extension
            for old_extension in self.settings.extensions
            if old_extension.identifier != extension.identifier
        ]
        self.manager.save()

    async def disable_extension(self, extension_identifier: str) -> None:
        extension = await self.extension_from_identifier(extension_identifier)
        if not extension:
            raise RuntimeError(f"Extension not found: {extension_identifier}")

        logger.info(f"Disabling: {extension_identifier}")

        extension.enabled = False
        self.settings.extensions = [
            installed_extension
            for installed_extension in self.settings.extensions
            if installed_extension.identifier != extension_identifier
        ]
        self.settings.extensions.append(extension)
        await self.remove(extension_identifier, False)
        self.manager.save()

    async def enable_extension(self, extension_identifier: str) -> None:
        extension = await self.extension_from_identifier(extension_identifier)
        if not extension:
            raise ExtensionNotFound(f"Extension not found: {extension_identifier}")

        logger.info(f"Enabling: {extension_identifier}")

        extension.enabled = True
        self.settings.extensions = [
            installed_extension
            for installed_extension in self.settings.extensions
            if installed_extension.identifier != extension_identifier
        ]
        self.settings.extensions.append(extension)
        self.manager.save()

    async def restart_extension(self, extension_identifier: str) -> None:
        logger.info(f"Going to restart {extension_identifier}.")
        await self.remove(extension_identifier, False)

    async def list_containers(self) -> List[DockerContainer]:
        containers: List[DockerContainer] = await self.client.containers.list(filter='{"status": ["running"]}')  # type: ignore
        return containers

    async def stream_logs(self, container_name: str, timeout: int = 30) -> AsyncGenerator[str, None]:
        containers = await self.client.containers.list(filters={"name": {container_name: True}})  # type: ignore
        if not containers:
            raise RuntimeError(f"Container not found: {container_name}")

        start_time = asyncio.get_event_loop().time()
        async for log_line in containers[0].log(stdout=True, stderr=True, follow=True, stream=True):
            elapsed_time = asyncio.get_event_loop().time() - start_time
            if elapsed_time > timeout:
                break
            yield log_line
        logger.info(f"Finished streaming logs for {container_name}")

    # pylint: disable=too-many-locals
    async def load_stats(self) -> Dict[str, Any]:
        containers = await self.client.containers.list()  # type: ignore

        # Create separate lists of coroutine objects for stats and show
        stats_coroutines = [container.stats(stream=False) for container in containers]
        show_coroutines = [container.show(size=1) for container in containers]

        # Run all stats and show coroutine objects concurrently
        stats_results = await asyncio.gather(*stats_coroutines)
        show_results = await asyncio.gather(*show_coroutines)

        # Extract the relevant data from the results
        container_stats = [result[0] for result in stats_results]
        container_shows = list(show_results)

        result = {}
        total_disk_size = psutil.disk_usage("/").total
        for stats, show in zip(container_stats, container_shows):
            # Based over: https://github.com/docker/cli/blob/v20.10.20/cli/command/container/stats_helpers.go
            cpu_percent = 0

            previous_cpu = stats["precpu_stats"]["cpu_usage"]["total_usage"]
            previous_system_cpu = stats["precpu_stats"]["system_cpu_usage"]

            cpu_total = stats["cpu_stats"]["cpu_usage"]["total_usage"]
            cpu_delta = cpu_total - previous_cpu

            cpu_system = stats["cpu_stats"]["system_cpu_usage"]
            system_delta = cpu_system - previous_system_cpu

            if system_delta > 0.0:
                cpu_percent = (cpu_delta / system_delta) * 100.0

            try:
                memory_usage = 100 * stats["memory_stats"]["usage"] / stats["memory_stats"]["limit"]
            except KeyError:
                memory_usage = "N/A"

            try:
                disk_usage = 100 * show["SizeRootFs"] / total_disk_size
            except KeyError:
                disk_usage = "N/A"

            name = stats["name"].replace("/", "")

            result[name] = {
                "cpu": cpu_percent,
                "memory": memory_usage,
                "disk": disk_usage,
            }
        return result

    async def stop(self) -> None:
        self.should_run = False
