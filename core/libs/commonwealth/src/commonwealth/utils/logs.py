import logging
from datetime import datetime, timezone
from logging import LogRecord
from pathlib import Path
from types import FrameType
from typing import Any, Optional, TextIO, Union, Callable

import zenoh
from loguru import logger, _handler


class LogRotator:
    def __init__(self, period_seconds: int):
        self._last_time = datetime.now(timezone.utc)
        self._period_seconds = period_seconds

    def should_rotate(self, message: Any, _file: TextIO) -> bool:
        if (message.record["time"] - self._last_time).total_seconds() > self._period_seconds:
            self._last_time = datetime.now(timezone.utc)
            return True
        return False


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


def get_new_log_path(service_name: str) -> Path:
    """Get default Path to a new log for a given service."""

    # Create folder for service logs if it doesn't exist yet
    default_log_folder = Path("/var/logs/blueos/services")
    service_log_folder = default_log_folder.joinpath(service_name)
    service_log_folder.mkdir(parents=True, exist_ok=True)

    # Returned log path are service-specific and store datetime information
    datetime_now = datetime.now().strftime("%Y%m%d_%H%M%S")
    return service_log_folder.joinpath(f"logfile_{datetime_now}.log")


def init_logger(service_name: str) -> None:
    try:
        validate_service_name(service_name)
        logger.add(get_new_log_path(service_name), rotation="10 MB")
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


def create_log_sink(service_name: str) -> Callable[[_handler.Message], None]:
    """Create a loguru sink that publishes logs to a zenoh topic.

    Args:
        service_name: The name of the service to use in the topic path

    Returns:
        A function that can be used as a loguru sink
    """
    session = zenoh.open(zenoh.Config())
    topic = f"services/{service_name}/log"

    def sink(message: _handler.Message) -> None:
        session.put(topic, message)

    return sink
