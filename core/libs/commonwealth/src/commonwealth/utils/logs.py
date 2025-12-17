import json
import logging
from logging import LogRecord
from types import FrameType
from typing import TYPE_CHECKING, Callable, Optional, Union

import zenoh
from commonwealth.utils.events import events
from commonwealth.utils.process import get_process_name
from commonwealth.utils.zenoh_helper import ZenohSession
from loguru import logger

if TYPE_CHECKING:
    from loguru import Message


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


def init_logger(service_name: str) -> None:
    try:
        validate_service_name(service_name)
        events.initialize(service_name)
        logger.add(create_log_sink(service_name), serialize=True)
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


def create_log_sink(service_name: str) -> Callable[["Message"], None]:
    """Create a loguru sink that publishes logs to a zenoh topic.

    Args:
        service_name: The name of the service to use in the topic path

    Returns:
        A function that can be used as a loguru sink
    """
    zenoh_session = ZenohSession(service_name)
    topic = f"services/{service_name}/log"
    process_name = get_process_name()

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

        foxglove_log = {
            "timestamp": {
                "sec": total_ns // 1_000_000_000,
                "nsec": total_ns % 1_000_000_000
            },
            "level": LEVEL_MAP.get(record["level"].name.upper(), LEVEL_MAP["UNKNOWN"]),
            "message": record["message"],
            "name": zenoh_session.format_source_name(process_name),
            "file": record["file"].name,
            "line": record["line"],
        }

        try:
            if zenoh_session.session is not None:
                zenoh_session.session.put(
                    topic,
                    json.dumps(foxglove_log),
                    encoding=zenoh.Encoding.APPLICATION_JSON.with_schema("foxglove.Log"),
                )
        except Exception as e:
            logger.debug(f"Failed to publish log to zenoh session: {e}")
        # fmt: on

    return sink
