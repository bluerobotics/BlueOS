from typing import Any, List

from commonwealth.utils.zenoh_helper import ZenohRouter
from extension_logs import ExtensionLogPublisher
from harbor import ContainerManager
from loguru import logger
from settings import get_extension_settings


class ContainerHandlers:
    def __init__(self, router: ZenohRouter) -> None:
        self.router = router

    async def logs_request_handler(self, extension_name: str) -> dict[str, Any]:
        if not extension_name:
            return {"error": "extension_name parameter is required"}

        try:
            extensions = get_extension_settings()
            extension = next(
                (ext for ext in extensions if extension_name in (ext.identifier, ext.name)),
                None,
            )

            if not extension:
                return {"error": f"Extension {extension_name} not found"}

            if not extension.enabled:
                return {"error": f"Extension {extension_name} is not enabled"}

            topic = ExtensionLogPublisher._topic_for(extension)

            container_name = extension.container_name()

            raw_logs = await ContainerManager.get_container_historical_logs(container_name)
            formatted_messages = []
            for raw_line in raw_logs:
                level, _ = ExtensionLogPublisher._extract_level(raw_line)
                formatted_messages.append(
                    {
                        "level": level,
                        "message": raw_line,
                    }
                )
            return {
                "status": "success",
                "messages": formatted_messages,
                "total_lines": len(formatted_messages),
                "topic": topic,
            }
        except Exception as e:
            logger.exception(f"Error handling logs request for {extension_name}")
            return {"error": str(e), "error_type": type(e).__name__}

    async def list_containers_handler(self) -> List[dict[str, Any]]:
        """
        List all running containers.
        """
        containers = await ContainerManager.get_running_containers()
        return [container.dict() for container in containers]

    async def container_stats_handler(self) -> dict[str, dict[str, Any]]:
        """
        List stats of all running containers.
        """
        stats = await ContainerManager.get_containers_stats()
        return {name: usage.dict() for name, usage in stats.items()}

    def register_queryables(self) -> None:
        self.router.add_queryable("container/logs/request", self.logs_request_handler)
        self.router.add_queryable("container/fetch", self.list_containers_handler)
        self.router.add_queryable("container/stats", self.container_stats_handler)
