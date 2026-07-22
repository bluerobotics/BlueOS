import json
import logging
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from logging import LogRecord
from types import FrameType
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Union

import zenoh
from commonwealth.utils.zenoh_helper import ZenohRouter, ZenohSession
from loguru import logger

if TYPE_CHECKING:
    from loguru import Message, Record

LOG_PUBLISHER_OPTIONS: dict[str, Any] = {
    "encoding": zenoh.Encoding.APPLICATION_JSON.with_schema("foxglove.Log"),
    "congestion_control": zenoh.CongestionControl.BLOCK,
    "priority": zenoh.Priority.DATA,
}

# Set at service boundaries (request middleware, Service.read/write, tasks) so deep
# modules can keep using `from loguru import logger` under co-location.
_service_logging_name: ContextVar[Optional[str]] = ContextVar("service_logging_name", default=None)


@contextmanager
def service_logging_context(service_name: str) -> Generator[None, None, None]:
    token = _service_logging_name.set(service_name)
    try:
        yield
    finally:
        _service_logging_name.reset(token)


class InterceptHandler(logging.Handler):
    def emit(self, record: LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        level: Union[int, str]
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame: Optional[FrameType]
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def validate_service_name(service_name: str) -> None:
    """Validate the service name."""
    if service_name == "":
        raise ValueError("Service name cannot be empty")
    if "/" in service_name:
        raise ValueError("Service name cannot contain forward slash character ('/').")
    if "." in service_name:
        raise ValueError("Service name cannot contain extension-separation character ('.').")


def _coerce_level(level: Union[str, int]) -> int:
    if isinstance(level, int):
        return level
    return logger.level(level).no


def _level_name(level_no: int) -> str:
    for name in ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"):
        if logger.level(name).no == level_no:
            return name
    return str(level_no)


class ServiceLogging:
    """Per-service zenoh log sink with a level that can change at runtime."""

    def __init__(self, service_name: str, level: Union[str, int] = "DEBUG") -> None:
        validate_service_name(service_name)
        self.service_name = service_name
        self._level_no = _coerce_level(level)
        self._handler_id: Optional[int] = None

    @property
    def level(self) -> str:
        return _level_name(self._level_no)

    def set_level(self, value: Union[str, int]) -> None:
        self._level_no = _coerce_level(value)

    def filter(self, record: "Record") -> bool:
        service = record["extra"].get("service") or _service_logging_name.get() or self.service_name
        if service != self.service_name:
            return False
        return record["level"].no >= self._level_no

    def setup(self, session: ZenohSession | None = None) -> None:
        if self._handler_id is not None:
            return
        # Legacy callers (init_logger) pass no session — open a dedicated one.
        self._handler_id = logger.add(
            create_log_sink(self.service_name, session),
            serialize=True,
            filter=self.filter,
        )

    def teardown(self) -> None:
        if self._handler_id is None:
            return
        logger.remove(self._handler_id)
        self._handler_id = None


def init_logger(service_name: str) -> None:
    try:
        ServiceLogging(service_name).setup()
    except Exception as e:
        print(f"Error: unable to set logging path: {e}")


def stack_trace_message(error: BaseException) -> str:
    """Get string containing joined messages from all exceptions in stack trace, beginning with the most recent one."""
    message = str(error)
    sub_error = error.__cause__
    while sub_error is not None:
        message = f"{message} {sub_error}"
        sub_error = sub_error.__cause__
    return message


def create_log_sink(
    service_name: str,
    session: ZenohSession | None = None,
) -> Callable[["Message"], None]:
    """Create a loguru sink that publishes logs to a zenoh topic."""
    topic = f"services/{service_name}/log"
    publisher = ZenohRouter(service_name, session=session).add_publisher(
        topic,
        absolute=True,
        publisher_options=LOG_PUBLISHER_OPTIONS,
    )

    def sink(message: "Message") -> None:
        # Transform the message to the Foxglove log format
        # https://docs.foxglove.dev/docs/visualization/message-schemas/log

        # fmt: off
        LEVEL_MAP = {
            "UNKNOWN": 0, # Foxglove value
            "TRACE": 0,
            "DEBUG": 1,
            "INFO": 2, # Foxglove value
            "SUCCESS": 2,
            "WARNING": 3,
            "ERROR": 4,
            "FATAL": 5, # Foxglove value
            "CRITICAL": 5,
        }

        record = message.record
        total_ns = record["time"].timestamp() * 1e9

        # Foxglove Log has no exception field — append the traceback to the message.
        log_message = record["message"]
        exception = record["exception"]
        if exception is not None:
            log_message = (
                f"{log_message}\n"
                f"{''.join(traceback.format_exception(exception.type, exception.value, exception.traceback))}"
            )

        foxglove_log = {
            "timestamp": {
                "sec": total_ns // 1_000_000_000,
                "nsec": total_ns % 1_000_000_000
            },
            "level": LEVEL_MAP.get(record["level"].name.upper(), LEVEL_MAP["UNKNOWN"]),
            "message": log_message,
            "name": record["name"],
            "file": record["file"].name,
            "line": record["line"],
        }

        try:
            publisher.put(json.dumps(foxglove_log))
        except Exception as e:
            # Avoid logger.* here — this sink is on the logger and can recurse.
            print(f"Failed to publish log to {topic}: {e}")
        # fmt: on

    return sink
