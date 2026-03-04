import asyncio
import json
import time
from typing import Callable, Dict, Optional, Tuple

from commonwealth.utils.zenoh_helper import ZenohSession
from config import SERVICE_NAME
from extension.extension import Extension
from harbor import ContainerManager
from loguru import logger
from settings import ExtensionSettings


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
        self._zenoh_session = ZenohSession(SERVICE_NAME)
        self._tasks: Dict[str, asyncio.Task[None]] = {}

    async def sync_with_running_extensions(self) -> None:
        desired_streams = await self._collect_desired_streams()
        if desired_streams is None:
            return
        self._start_missing_streams(desired_streams)
        self._stop_removed_streams(desired_streams)

    async def shutdown(self) -> None:
        if not self._tasks:
            return
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()

    async def _collect_desired_streams(self) -> Optional[Dict[str, ExtensionSettings]]:
        try:
            running_containers = await ContainerManager.get_running_containers()
        except Exception as error:
            logger.debug(f"Unable to fetch running containers for extension logs: {error}")
            return None

        running_names = {container.name.lstrip("/") for container in running_containers}
        extensions = Extension._fetch_settings()

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

        try:
            async for raw_line in ContainerManager.get_container_log_by_name(container_name):
                payload = self._format_log_payload(container_name, raw_line.rstrip("\n"))
                self._publish(topic, payload)
        except asyncio.CancelledError:
            logger.debug(f"Extension log stream for {container_name} cancelled")
            raise
        except Exception as error:
            logger.debug(f"Extension log stream for {container_name} stopped: {error}")

    def _publish(self, topic: str, log_line: str) -> None:
        session = self._zenoh_session.session
        if session is None:
            return
        try:
            session.put(topic, log_line.encode("utf-8"))
        except Exception as error:
            logger.debug(f"Failed to publish extension log to {topic}: {error}")

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
