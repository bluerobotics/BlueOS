import asyncio
import os
import subprocess
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any, AsyncGenerator

import psutil
from loguru import logger

from commonwealth.utils.commands import load_file
from commonwealth.utils.decorators import temporary_cache


class CpuType(str, Enum):
    PI3 = "Raspberry Pi 3 (BCM2837)"
    PI4 = "Raspberry Pi 4 (BCM2711)"
    PI5 = "Raspberry Pi 5 (BCM2712)"
    Other = "Other"


class HostOs(str, Enum):
    Bookworm = "Debian(Raspberry Pi OS?) 12 (Bookworm)"
    Bullseye = "Debian(Raspberry Pi OS?) 11 (Bullseye)"
    Other = "Other"


@cache
def blueos_version() -> str:
    return os.environ.get("GIT_DESCRIBE_TAGS", "null")


@cache
def get_cpu_type() -> CpuType:
    with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
        for line in f:
            if "Raspberry Pi 4" in line:
                return CpuType.PI4
            if "Raspberry Pi 5" in line:
                return CpuType.PI5
            if "Raspberry Pi 3" in line:
                return CpuType.PI3
    return CpuType.Other


@cache
def get_host_os() -> HostOs:
    os_release = load_file("/etc/os-release")
    if "bookworm" in os_release.lower():
        return HostOs.Bookworm
    if "bullseye" in os_release.lower():
        return HostOs.Bullseye
    return HostOs.Other


def delete_everything(path: Path) -> None:
    if path.is_file() and (path.suffix == ".gz" or not file_is_open(path)):
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


@dataclass
class DeletionInfo:
    path: str
    size: int
    type: str
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def delete_everything_stream(path: Path) -> AsyncGenerator[dict[str, Any], None]:
    """Delete everything in a path and yield information about each file being deleted.

    Args:
        path: Path to delete

    Yields:
        Dictionary containing information about each file being deleted:
        {
            'path': str,  # Path of the file being deleted
            'size': int,  # Size of the file in bytes
            'type': str,  # 'file' or 'directory'
            'success': bool  # Whether deletion was successful
        }
    """

    if path.is_file() and not file_is_open(path):
        try:
            size = path.stat().st_size
            await asyncio.to_thread(path.unlink)
            # fmt: off
            yield DeletionInfo(
                path=str(path),
                size=size,
                type="file",
                success=True
            ).to_dict()
            # fmt: on
        except Exception as exception:
            logger.warning(f"Failed to delete: {path}, {exception}")
            # fmt: off
            yield DeletionInfo(
                path=str(path),
                size=0,
                type="file",
                success=False
            ).to_dict()
            # fmt: on
        return

    items = await asyncio.to_thread(lambda: list(path.glob("*")))

    for item in items:
        try:
            if item.is_file() and not file_is_open(item):
                size = item.stat().st_size
                await asyncio.to_thread(item.unlink)
                # fmt: off
                yield DeletionInfo(
                    path=str(item),
                    size=size,
                    type="file",
                    success=True
                ).to_dict()
                # fmt: on
            if item.is_dir() and not item.is_symlink():
                # Delete folder contents
                async for info in delete_everything_stream(item):
                    yield info
        except Exception as exception:
            logger.warning(f"Failed to delete: {item}, {exception}")
            # fmt: off
            yield DeletionInfo(
                path=str(item),
                size=0,
                type="directory" if item.is_dir() else "file",
                success=False
            ).to_dict()
            # fmt: on


def file_is_open(path: Path) -> bool:
    try:
        kernel_functions_timeout = str(2)
        result = subprocess.run(
            ["lsof", "-t", "-n", "-P", "-S", kernel_functions_timeout, path.resolve()],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=5,
        )
        return result.returncode == 0
    except Exception as error:
        logger.error(f"Failed to check if file {path} is open, {error}")
        return True


@cache
def local_unique_identifier() -> str:
    blueos_uuid_path = "/etc/blueos/uuid"

    # Try to get an uuid4 from BlueOS of previous boots
    try:
        with open(blueos_uuid_path, "r", encoding="utf-8") as f:
            uuid4 = "".join(f.read().split())
            try:
                uuid.UUID(uuid4, version=4)
                return uuid4
            except ValueError:
                logger.warning(f"Local BlueOS uuid is not valid: {uuid4}")
    except Exception as error:
        logger.warning(f"Could not get BlueOS's uuid. {error}")

    # We failed, going to generate a new BlueOS uuid
    uuid4 = uuid.uuid4().hex
    try:
        with open(blueos_uuid_path, "w+", encoding="utf-8") as f:
            f.write(uuid4)
            f.flush()
        return uuid4
    except Exception as error:
        logger.warning(f"Failed to write uuid {uuid4} to {blueos_uuid_path}, {error}")

    # There is something really wrong here and this line should never run
    # But at least we are going to identify that something is wrong
    return "00000000000040000000000000000000"


@cache
def local_hardware_identifier() -> str:
    blueos_uuid_path = "/etc/blueos/hardware-uuid"

    # Try to get an uuid from hardware configuration
    try:
        with open(blueos_uuid_path, "r", encoding="utf-8") as f:
            hardware_uuid = "".join(f.read().split())
            try:
                uuid.UUID(hardware_uuid)
                return hardware_uuid
            except ValueError:
                logger.warning(f"Local hardware uuid is not valid: {hardware_uuid}")
    except Exception as error:
        logger.warning(f"Could not get hardware uuid. {error}")

    # There is something really wrong here and this line should never run
    # But at least we are going to identify that something is wrong
    return "00000000000030000000000000000000"


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


@temporary_cache(timeout_seconds=600)  # type: ignore
def available_disk_space_mb() -> float:
    # Make mypy happy
    return float(psutil.disk_usage("/").free / (2**20))
