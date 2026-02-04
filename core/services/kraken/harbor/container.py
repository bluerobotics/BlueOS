import asyncio
from typing import AsyncGenerator, Dict, List

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

    @staticmethod
    async def get_running_containers() -> List[ContainerModel]:
        async with DockerCtx() as client:
            containers = await client.containers.list(filters={"status": ["running"]})  # type: ignore

            return [
                ContainerModel(
                    name=container["Names"][0],
                    image=container["Image"],
                    image_id=container["ImageID"],
                    status=container["Status"],
                )
                for container in containers
            ]

    @classmethod
    async def get_running_container_by_name(cls, container_name: str) -> ContainerModel:
        async with DockerCtx() as client:
            container = await cls.get_raw_container_by_name(client, container_name)

            return ContainerModel(
                name=container["Names"][0],
                image=container["Image"],
                image_id=container["ImageID"],
                status=container["Status"],
            )

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
