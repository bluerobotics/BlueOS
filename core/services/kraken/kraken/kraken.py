import asyncio
import psutil
from dataclasses import asdict
from typing import List, Dict, Any, AsyncGenerator, cast
from aiodocker.docker import DockerContainer
# Package
from config import SERVICE_NAME
# Kraken
from kraken.docker import DockerCtx, DockerContainerUsage
# Manifest
from manifest import Manifest
# Settings
from commonwealth.settings.manager import Manager
from settings import Extension as ExtensionSettings, SettingsV1

class Kraken:
    manager = Manager(SERVICE_NAME, SettingsV1)
    settings = manager.settings
    manifest = Manifest.instance()

    # TODO - Add main check loop

    @staticmethod
    async def installed_extensions() -> List[ExtensionSettings]:
        return cast(List[ExtensionSettings], Kraken.settings.extensions)


    @staticmethod
    async def fetch_manifest() -> List[Dict[str, Any]]:
        return [asdict(extension) for extension in await Kraken.manifest.fetch()]


    @staticmethod
    def has_enough_disk_space(required_bytes: int, path: str = "/") -> bool:
        try:
            free_space = psutil.disk_usage(path).free
            return bool(free_space > required_bytes)
        except FileNotFoundError:
            return False


    @staticmethod
    async def list_containers() -> List[DockerContainer]:
        async with DockerCtx() as client:
            return await client.containers.list(filter='{"status": ["running"]}')  # type: ignore


    @staticmethod
    async def log(container_name: str, timeout: int = 30) -> AsyncGenerator[str, None]:
        async with DockerCtx() as client:
            containers = await client.containers.list(filters={"name": {container_name: True}})
            if not containers:
                raise RuntimeError(f"Container not found: {container_name}")

            async with asyncio.wait_for(containers[0].logs(stdout=True, stderr=True, follow=True), timeout) as logs:
                async for log in logs:
                    yield log


    @staticmethod
    async def stats() -> Dict[str, DockerContainerUsage]:
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

                result[name] = DockerContainerUsage(
                    cpu_percent,
                    memory_usage,
                    disk_usage,
                )

            return result
