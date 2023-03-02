import os
import subprocess
from pathlib import Path

from loguru import logger


def delete_everything(path: Path) -> None:
    if path.is_file() and not file_is_open(path):
        path.unlink()
        return

    for item in path.glob("*"):
        try:
            if item.is_file() and not file_is_open(item):
                item.unlink()
            if item.is_dir() and not item.is_symlink():
                # Delete folder contents
                delete_everything(item)
        except Exception as exception:
            logger.warning(f"Failed to delete: {item}, {exception}")


def file_is_open(path: Path) -> bool:
    result = subprocess.run(["lsof", path.resolve()], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.returncode == 0


def is_running_as_root() -> bool:
    return os.geteuid() == 0


def device_id() -> str:
    try:
        with open("/sys/firmware/devicetree/base/serial-number", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as error:
        logger.exception(f"Could not get device's serial-number. {error}")

    try:
        with open("/etc/machine-id", "r", encoding="utf-8") as f:
            return "".join(f.read().split())
    except Exception as error:
        logger.exception(f"Could not get device's machine-id. {error}")

    raise ValueError("Could not get device id.")
