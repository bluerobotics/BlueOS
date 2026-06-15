import asyncio
import json
import time
from typing import Callable, Dict, Optional, Tuple

import zenoh
from commonwealth.utils.logs import LOG_PUBLISHER_OPTIONS
from commonwealth.utils.zenoh_helper import ZenohRouter
from config import SERVICE_NAME
from harbor import ContainerManager
from loguru import logger
from settings import ExtensionSettings, get_extension_settings


class ExtensionLogPublisher:
    _LEVEL_MAP: Dict[str, int] = {
        "FATAL": 5,
        "ERROR": 4,
        "ERR": 4,
        "WARNING": 3,
        "WARN": 3,
        "INFO": 2,
        "DEBUG": 1,
        "TRACE": 1,
        "UNKNOWN": 0,
    }

    def __init__(self) -> None:
        self._zenoh_router = ZenohRouter(SERVICE_NAME)
        self._publishers: Dict[str, zenoh.Publisher] = {}
        self._tasks: Dict[str, asyncio.Task[None]] = {}

    async def sync_with_running_extensions(self) -> None:
        desired_streams = await self._collect_desired_streams()
        if desired_streams is None:
            return
        self._start_missing_streams(desired_streams)
        self._stop_removed_streams(desired_streams)

    async def shutdown(self) -> None:
        if self._tasks:
            for task in self._tasks.values():
                task.cancel()
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
            self._tasks.clear()
        self._undeclare_publishers()

    async def _collect_desired_streams(self) -> Optional[Dict[str, ExtensionSettings]]:
        try:
            running_containers = await ContainerManager.get_running_containers()
        except Exception as error:
            logger.debug(f"Unable to fetch running containers for extension logs: {error}")
            return None

        running_names = {container.name.lstrip("/") for container in running_containers}
        extensions = get_extension_settings()

        desired: Dict[str, ExtensionSettings] = {}
        for extension in extensions:
            if not extension.enabled:
                continue
            container_name = extension.container_name()
            if container_name in running_names:
                desired[container_name] = extension
        return desired

    def _start_missing_streams(self, desired_streams: Dict[str, ExtensionSettings]) -> None:
        for container_name, extension in desired_streams.items():
            if container_name in self._tasks:
                continue
            task = asyncio.create_task(self._stream_logs(extension))
            task.add_done_callback(self._make_cleanup_callback(container_name))
            self._tasks[container_name] = task

    def _stop_removed_streams(self, desired_streams: Dict[str, ExtensionSettings]) -> None:
        for container_name in list(self._tasks.keys()):
            if container_name in desired_streams:
                continue
            task = self._tasks.pop(container_name)
            task.cancel()

    def _make_cleanup_callback(self, container_name: str) -> Callable[[asyncio.Task[None]], None]:
        def _cleanup(task: asyncio.Task[None]) -> None:
            saved = self._tasks.get(container_name)
            if saved is task:
                self._tasks.pop(container_name, None)
            if task.cancelled():
                return
            exception = task.exception()
            if exception:
                logger.debug(f"Extension log stream for {container_name} ended with error: {exception}")

        return _cleanup

    async def _stream_logs(self, extension: ExtensionSettings) -> None:
        container_name = extension.container_name()
        topic = self._topic_for(extension)
        logger.debug(f"Starting extension log stream for {container_name} -> {topic}")

        publisher = self._declare_publisher(container_name, extension)
        if publisher is None:
            logger.debug(f"Unable to declare extension log publisher for {container_name}")
            return

        try:
            async for raw_line in ContainerManager.get_container_log_by_name(container_name):
                payload = self._format_log_payload(container_name, raw_line.rstrip("\n"))
                self._publish(publisher, topic, payload)
        except asyncio.CancelledError:
            logger.debug(f"Extension log stream for {container_name} cancelled")
            raise
        except Exception as error:
            logger.debug(f"Extension log stream for {container_name} stopped: {error}")
        finally:
            self._undeclare_publisher(container_name)

    def _publish(self, publisher: zenoh.Publisher, topic: str, log_line: str) -> None:
        try:
            publisher.put(log_line)
        except Exception as error:
            logger.debug(f"Failed to publish extension log to {topic}: {error}")

    def _declare_publisher(self, container_name: str, extension: ExtensionSettings) -> zenoh.Publisher | None:
        if container_name in self._publishers:
            return self._publishers[container_name]

        publisher = self._zenoh_router.add_publisher(
            self._topic_for(extension),
            absolute=True,
            publisher_options=LOG_PUBLISHER_OPTIONS,
        )
        if publisher is not None:
            self._publishers[container_name] = publisher
        return publisher

    def _undeclare_publisher(self, container_name: str) -> None:
        publisher = self._publishers.pop(container_name, None)
        if publisher is None:
            return
        try:
            publisher.undeclare()  # type: ignore[no-untyped-call]
        except Exception as error:
            logger.debug(f"Failed to undeclare extension log publisher for {container_name}: {error}")

    def _undeclare_publishers(self) -> None:
        for container_name in list(self._publishers.keys()):
            self._undeclare_publisher(container_name)

    @staticmethod
    def _topic_for(extension: ExtensionSettings) -> str:
        name = extension.identifier or extension.name or extension.container_name()
        safe_name = name.replace("/", "_").replace(" ", "_")
        return f"extensions/logs/{safe_name}"

    @classmethod
    def _format_log_payload(cls, container_name: str, message: str) -> str:
        level, normalized_message = cls._extract_level(message)
        seconds, nanos = divmod(time.time_ns(), 1_000_000_000)
        payload = {
            "timestamp": {"sec": seconds, "nsec": nanos},
            "level": level,
            "message": normalized_message,
            "name": container_name,
            "file": "",
            "line": 0,
        }
        return json.dumps(payload)

    @classmethod
    def _extract_level(cls, message: str) -> Tuple[int, str]:
        stripped = message.lstrip()
        upper = stripped.upper()
        for name, level in cls._LEVEL_MAP.items():
            prefixes = (
                f"{name}:",
                f"{name} ",
                f"[{name}]",
                f"{name}|",
            )
            for prefix in prefixes:
                if upper.startswith(prefix):
                    remainder = stripped[len(prefix) :].lstrip()
                    return level, remainder or stripped
        return 0, stripped
