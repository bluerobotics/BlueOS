from typing import Any, List, cast

from commonwealth.utils.zenoh_helper import ZenohRouter
from extension.extension import Extension
from extension_logs import ExtensionLogPublisher
from harbor import ContainerManager
from loguru import logger
from settings import ExtensionSettings


class ZenohHandlers:
    def __init__(self, router: ZenohRouter) -> None:
        self.router = router

    async def logs_request_handler(self, extension_name: str) -> dict[str, Any]:
        if not extension_name:
            return {"error": "extension_name parameter is required"}

        try:
            extensions = cast(List[ExtensionSettings], Extension._fetch_settings())
            extension = next((ext for ext in extensions if extension_name in (ext.identifier, ext.name)), None)

            if not extension:
                return {"error": f"Extension {extension_name} not found"}

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

    def register_queryables(self) -> None:
        self.router.add_queryable("extension/logs/request", self.logs_request_handler)
