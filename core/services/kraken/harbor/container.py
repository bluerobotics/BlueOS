import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List

import psutil
from aiodocker import Docker
from aiodocker.containers import DockerContainer
from commonwealth.utils.apis import StackedHTTPException
from fastapi import status
from harbor.contexts import DockerCtx
from harbor.exceptions import ContainerNotFound
from harbor.models import ContainerModel, ContainerUsageModel
from loguru import logger


class ContainerManager:
    @staticmethod
    def _human_duration(duration_seconds: float) -> str:
        seconds = int(duration_seconds)
        if seconds < 1:
            human_duration = "Less than a second"
        elif seconds == 1:
            human_duration = "1 second"
        elif seconds < 60:
            human_duration = f"{seconds} seconds"
        else:
            minutes = int(duration_seconds / 60)
            hours = int(duration_seconds / 60 / 60 + 0.5)
            if minutes == 1:
                human_duration = "About a minute"
            elif minutes < 60:
                human_duration = f"{minutes} minutes"
            elif hours == 1:
                human_duration = "About an hour"
            elif hours < 48:
                human_duration = f"{hours} hours"
            elif hours < 24 * 7 * 2:
                human_duration = f"{hours // 24} days"
            elif hours < 24 * 30 * 2:
                human_duration = f"{hours // 24 // 7} weeks"
            elif hours < 24 * 365 * 2:
                human_duration = f"{hours // 24 // 30} months"
            else:
                human_duration = f"{int(duration_seconds / 60 / 60) // 24 // 365} years"

        return human_duration

    @classmethod
    def _status_with_monotonic_uptime(cls, status_text: str, pid: int) -> str:
        if not status_text.startswith("Up ") or pid <= 0:
            return status_text

        try:
            process_start_since_boot = psutil.Process(pid).create_time() - psutil.boot_time()
            uptime_seconds = max(0.0, time.monotonic() - process_start_since_boot)
        except psutil.Error:
            return status_text

        suffix_start = status_text.find(" (")
        suffix = status_text[suffix_start:] if suffix_start >= 0 else ""
        return f"Up {cls._human_duration(uptime_seconds)}{suffix}"

    @classmethod
    def _container_model(cls, container: DockerContainer, details: Dict[str, Any]) -> ContainerModel:
        pid = details.get("State", {}).get("Pid", 0)
        return ContainerModel(
            name=container["Names"][0],
            image=container["Image"],
            image_id=container["ImageID"],
            status=cls._status_with_monotonic_uptime(container["Status"], pid),
        )

    @staticmethod
    async def get_raw_container_by_name(client: Docker, container_name: str) -> DockerContainer:
        containers = await client.containers.list(filters={"name": {container_name: True}})  # type: ignore
        if not containers:
            raise ContainerNotFound(f"Container {container_name} not found in running containers")

        return containers[0]

    @staticmethod
    async def kill_all_by_name(client: Docker, container_name: str) -> None:
        logger.info(f"Killing container {container_name}")
        containers = await client.containers.list(filters={"name": {container_name: True}})  # type: ignore
        for container in containers:
            await container.kill()
            await container.wait()

    @staticmethod
    # pylint: disable=too-many-locals
    async def _get_stats_from_containers(containers: List[DockerContainer]) -> Dict[str, ContainerUsageModel]:
        result: Dict[str, ContainerUsageModel] = {}

        # Create separate lists of coroutine objects for stats and show
        stats_coroutines = [container.stats(stream=False) for container in containers]  # type: ignore
        show_coroutines = [container.show(size=1) for container in containers]  # type: ignore

        # Run all stats and show coroutine objects concurrently
        stats_results, show_results = await asyncio.gather(
            asyncio.gather(*stats_coroutines), asyncio.gather(*show_coroutines)
        )

        # Extract the relevant data from the results
        container_stats = [result[0] for result in stats_results if result]
        container_shows = list(show_results)

        total_disk_size = psutil.disk_usage("/").total
        for stats, show in zip(container_stats, container_shows):
            # Based over: https://github.com/docker/cli/blob/v20.10.20/cli/command/container/stats_helpers.go
            cpu_percent = 0

            previous_cpu = stats.get("precpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            previous_system_cpu = stats.get("precpu_stats", {}).get("system_cpu_usage", 0)

            cpu_total = stats.get("cpu_stats", {}).get("cpu_usage", {}).get("total_usage", 0)
            cpu_delta = cpu_total - previous_cpu

            cpu_system = stats.get("cpu_stats", {}).get("system_cpu_usage", 0)
            system_delta = cpu_system - previous_system_cpu

            if system_delta > 0.0 and cpu_delta > 0.0:
                cpu_percent = (cpu_delta / system_delta) * 100.0

            try:
                memory_usage = 100 * stats["memory_stats"]["usage"] / stats["memory_stats"]["limit"]
            except KeyError:
                memory_usage = "N/A"

            try:
                disk_usage = 100 * show["SizeRootFs"] / total_disk_size
            except KeyError:
                disk_usage = "N/A"

            name = stats.get("name", "unknown").replace("/", "")

            result[name] = ContainerUsageModel(
                cpu=cpu_percent,
                memory=memory_usage,
                disk=disk_usage,
            )

        return result

    @classmethod
    async def get_running_containers(cls) -> List[ContainerModel]:
        async with DockerCtx() as client:
            containers = await client.containers.list(filters={"status": ["running"]})  # type: ignore
            details = await asyncio.gather(*(container.show() for container in containers))

            return [cls._container_model(container, detail) for container, detail in zip(containers, details)]

    @classmethod
    async def get_running_container_by_name(cls, container_name: str) -> ContainerModel:
        async with DockerCtx() as client:
            container = await cls.get_raw_container_by_name(client, container_name)
            details = await container.show()

            return cls._container_model(container, details)

    @classmethod
    async def get_container_log_by_name(cls, container_name: str) -> AsyncGenerator[str, None]:
        async with DockerCtx(timeout=0) as client:
            try:
                container = await cls.get_raw_container_by_name(client, container_name)
            except ContainerNotFound as error:
                raise StackedHTTPException(status_code=status.HTTP_404_NOT_FOUND, error=error) from error

            async for log_line in container.log(stdout=True, stderr=True, follow=True, stream=True):  # type: ignore
                yield log_line
            logger.info(f"Finished streaming logs for {container_name}")

    @classmethod
    async def get_container_historical_logs(cls, container_name: str) -> List[str]:
        async with DockerCtx() as client:
            try:
                container = await cls.get_raw_container_by_name(client, container_name)
            except ContainerNotFound as error:
                raise StackedHTTPException(status_code=status.HTTP_404_NOT_FOUND, error=error) from error

            return await container.log(stdout=True, stderr=True, follow=False, stream=False)  # type: ignore

    @classmethod
    async def get_containers_stats(cls) -> Dict[str, ContainerUsageModel]:
        async with DockerCtx() as client:
            containers = await client.containers.list()  # type: ignore

            return await cls._get_stats_from_containers(containers)

    @classmethod
    async def get_container_stats_by_name(cls, container_name: str) -> ContainerUsageModel:
        async with DockerCtx() as client:
            container = await cls.get_raw_container_by_name(client, container_name)

            result = await cls._get_stats_from_containers([container])

            return next(iter(result.values()))
