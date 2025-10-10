import gzip
import json
import logging
import subprocess
from logging import LogRecord
from pathlib import Path
from types import FrameType
from typing import Optional, TYPE_CHECKING, Union, Callable

import zenoh
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


def get_new_log_path(service_name: str) -> Path:
    """Get default Path to a new log for a given service."""

    # Create folder for service logs if it doesn't exist yet
    default_log_folder = Path("/var/logs/blueos/services")
    service_log_folder = default_log_folder.joinpath(service_name)
    service_log_folder.mkdir(parents=True, exist_ok=True)

    # Returned log path are service-specific
    return service_log_folder.joinpath(f"{service_name}.log")


def custom_compression(path: str) -> None:
    archive_path = f"{path}-{get_last_boot_timestamp()}.gz"
    with open(path, "rb") as file:
        with gzip.open(archive_path, "wb") as compressed:
            compressed.writelines(file)


def get_last_boot_timestamp() -> str:
    boot_info = subprocess.check_output(["journalctl", "--list-boots"], encoding="utf-8").splitlines()
    # if the bind has not occurred journalctl will be empty
    if not boot_info or len(boot_info) < 2:
        return ""
    last_boot_info = boot_info[-2]
    clean_info = last_boot_info.lstrip().split(" ")

    try:
        date = clean_info[3]
        time = clean_info[4]
        timezone = clean_info[-1]
        # format: "YYYY-MM-DDTHH:MM:SSZ"
        return f"{date}T{time}{timezone}"
    except (IndexError, ValueError):
        return ""


def init_logger(service_name: str) -> None:
    try:
        validate_service_name(service_name)
        logger.add(get_new_log_path(service_name), compression=custom_compression)
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
    zenoh_config = zenoh.Config()
    zenoh_config.insert_json5("adminspace", json.dumps({"enabled": True}))
    zenoh_config.insert_json5("metadata", json.dumps({"name": service_name}))
    zenoh_config.insert_json5("mode", json.dumps("client"))
    zenoh_config.insert_json5("connect/endpoints", json.dumps(["tcp/127.0.0.1:7447"]))
    session = zenoh.open(zenoh_config)
    topic = f"services/{service_name}/log"

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
            "name": record["name"],
            "file": record["file"].name,
            "line": record["line"],
        }

        session.put(
            topic,
            json.dumps(foxglove_log),
            encoding=zenoh.Encoding.APPLICATION_JSON.with_schema("foxglove.Log"),
        )
        # fmt: on

    return sink
