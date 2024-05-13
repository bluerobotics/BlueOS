import asyncio
import psutil
from dataclasses import asdict
from typing import Any, AsyncGenerator, cast, Dict, List, Tuple

from aiodocker.docker import DockerContainer
from loguru import logger

from commonwealth.settings.manager import Manager
from config import SERVICE_NAME
from manifest import Manifest
from app.docker.docker import DockerCtx
from kraken.extension import Extension
from kraken.exceptions import ExtensionContainerNotFound, ExtensionNotFound
from kraken.models import ContainerUsageModel
from settings import Extension as ExtensionSettings, SettingsV1


class Kraken:
    """
    Kraken class for managing extensions and containers.
    """

    manager = Manager(SERVICE_NAME, SettingsV1)
    settings = manager.settings
    manifest = Manifest.instance()
    operation_in_progress = False


    def __init__(self) -> None:
        """
        Initialize Kraken instance.
        """

        self.is_running = True


    async def poll(self) -> None:
        """
        Polls all running containers and checks if they are compliant with current settings.
        """

        containers = await Kraken.list_containers()
        extensions = await Kraken.installed_extensions()

        for ext in extensions:
            if not ext.enabled:
                continue

            extension = Extension(ext.identifier, ext.tag)

            if not ext.is_valid():
                try:
                    await extension.uninstall()
                except (ExtensionContainerNotFound, ExtensionNotFound):
                    logger.warning(
                        f"Tried to uninstall invalid extension: {ext.identifier}:{ext.tag} but container was not found."
                    )
                continue

            extension_name = ext.container_name()
            if not any(container["Names"][0][1:] == extension_name for container in containers):
                await extension.start()


    async def start(self) -> None:
        """
        Starts main Kraken polling loop.
        """

        while self.should_run:
            await asyncio.sleep(5)

            # We only want to poll if there is no critical operation in progress like installing or
            # removing an extension since these can change container states.
            if not Kraken.operation_in_progress:
                await self.poll()


    async def stop(self) -> None:
        """
        Stops main Kraken polling loop.
        """

        self.is_running = False


    @staticmethod
    async def installed_extensions() -> List[ExtensionSettings]:
        """
        List all installed extensions.

        Returns:
            - List[ExtensionSettings]: List of installed extensions.
        """
        return cast(List[ExtensionSettings], Kraken.settings.extensions)


    @staticmethod
    async def fetch_manifest() -> List[Dict[str, Any]]:
        """
        Fetch the manifest of all extensions.

        Returns:
            - List[Dict[str, Any]]: List of extension manifest dictionaries.
        """

        return [asdict(extension) for extension in await Kraken.manifest.fetch()]


    @staticmethod
    def has_enough_disk_space(required_bytes: int, path: str = "/") -> bool:
        """
        Check if there is enough disk space to install an extension.

        Args:
            - required_bytes (int): Required disk space in bytes.
            - path (str): Path to check for disk space.

        Returns:
            - bool: True if there is enough disk space, False otherwise.
        """

        try:
            free_space = psutil.disk_usage(path).free
            return bool(free_space > required_bytes)
        except FileNotFoundError:
            return False


    @staticmethod
    async def list_containers() -> List[DockerContainer]:
        """
        List all running containers.

        Returns:
            - List[DockerContainer]: List of running containers.
        """

        async with DockerCtx() as client:
            return await client.containers.list(filter='{"status": ["running"]}')  # type: ignore


    @staticmethod
    async def log(container_name: str, timeout: int = 30) -> AsyncGenerator[str, None]:
        """
        Get logs of a container.

        Args:
            - container_name (str): Name of the container.
            - timeout (int): Timeout for log retrieval.

        Yields:
            - str: Log line.
        """

        async with DockerCtx() as client:
            containers = await client.containers.list(filters={"name": {container_name: True}})
            if not containers:
                raise RuntimeError(f"Container not found: {container_name}")

            async with asyncio.wait_for(containers[0].logs(stdout=True, stderr=True, follow=True), timeout) as logs:
                async for log in logs:
                    yield log


    @staticmethod
    async def stats() -> Dict[str, ContainerUsageModel]:
        """
        List stats of all running containers.

        Returns:
            - Dict[str, ContainerUsageModel]: Container stats, with name as key ContainerUsageModel as value.
        """

        async with DockerCtx() as client:
            containers = await client.containers.list()

            # Create separate lists of coroutine objects for stats and show
            stats_coroutines = [container.stats(stream=False) for container in containers]
            show_coroutines = [container.show(size=True) for container in containers]

            # Run all stats and show coroutine objects concurrently
            stats_results, show_results = await asyncio.gather(
                asyncio.gather(*stats_coroutines),
                asyncio.gather(*show_coroutines)
            )

            result = {}
            total_disk_size = psutil.disk_usage("/").total
            for stats, show in zip(stats_results, show_results):
                cpu_percent = 0

                previous_cpu = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                previous_system_cpu = stats.get("precpu_stats", {}).get("system_cpu_usage", 0)

                cpu_total = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
                cpu_delta = cpu_total - previous_cpu

                cpu_system = stats.get("cpu_stats", {}).get("system_cpu_usage", 0)
                system_delta = cpu_system - previous_system_cpu

                if system_delta > 0.0 and cpu_delta > 0:
                    cpu_percent = (cpu_delta / system_delta) * 100.0

                memory_usage = "N/A"
                if "memory_stats" in stats and "usage" in stats["memory_stats"] and "limit" in stats["memory_stats"]:
                    memory_usage = 100 * stats["memory_stats"]["usage"] / stats["memory_stats"]["limit"]

                disk_usage = "N/A"
                if "SizeRootFs" in show:
                    disk_usage = 100 * show["SizeRootFs"] / total_disk_size

                name = stats.get("name", "unknown").replace("/", "")

                result[name] = ContainerUsageModel(
                    cpu_percent,
                    memory_usage,
                    disk_usage,
                )

            return result
