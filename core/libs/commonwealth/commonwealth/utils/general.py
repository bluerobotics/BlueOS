import os
import subprocess
from pathlib import Path

from loguru import logger


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
