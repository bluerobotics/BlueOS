import logging
from datetime import datetime
from logging import LogRecord
from pathlib import Path
from types import FrameType
from typing import Optional, Union

from loguru import logger


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


def get_new_log_path(service_name: str) -> Path:
    """Get default Path to a new log for a given service."""
    # Prevent problematic service names
    if service_name == "":
        raise ValueError("Service name cannot be empty")
    if "/" in service_name:
        raise ValueError("Service name cannot contain forward slash character ('/').")
    if "." in service_name:
        raise ValueError("Service name cannot contain extension-separation character ('.').")

    # Create folder for service logs if it doesn't exist yet
    default_log_folder = Path("/var/logs/blueos/services")
    service_log_folder = default_log_folder.joinpath(service_name)
    service_log_folder.mkdir(parents=True, exist_ok=True)

    # Returned log path are service-specific and store datetime information
    datetime_now = datetime.now().strftime("%m-%d-%Y_%H:%M:%S")
    return service_log_folder.joinpath(f"logfile_{datetime_now}.log")
