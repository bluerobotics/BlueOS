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
from commonwealth.utils.commands import load_file
from commonwealth.utils.decorators import temporary_cache
from loguru import logger


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


def delete_everything(path: Path, ignore: list[Path] | None = None) -> None:
    if ignore is None:
        ignore = []

    def is_ignored(target: Path) -> bool:
        for ignored_path in ignore:
            try:
                ignored_resolved = ignored_path.resolve()
                target_resolved = target.resolve()
                try:
                    # If relative_to works, target is inside or equal to ignored_resolved
                    target_resolved.relative_to(ignored_resolved)
                    return True
                except ValueError:
                    # Not relative, so not in ignored path
                    continue
            except Exception:
                continue
        return False

    if is_ignored(path):
        return

    if path.is_file() and not file_is_open(path):
        path.unlink()
        return

    for item in path.glob("*"):
        if is_ignored(item):
            continue
        try:
            if item.is_file() and not file_is_open(item):
                item.unlink()
            if item.is_dir() and not item.is_symlink():
                # Delete folder contents
                delete_everything(item, ignore=ignore)
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
            if item.is_file() and (item.suffix == ".gz" or not file_is_open(item)):
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


def _file_is_open_command(path: Path) -> list[str]:
    # fmt: off
    return [
        "lsof",
        "-t",       # output only PIDs (terse)
        "-n",       # do NOT resolve hostnames (faster, avoids DNS)
        "-P",       # do NOT resolve ports to service names
        "-S", "2",  # kernel function timeout = 2 seconds
        "--",       # stop option parsing, treat next as path
        str(path.resolve()),
    ]
    # fmt: on


def _file_is_open_logic_lsof(returncode: int | None, stdout: str, stderr: str) -> bool:
    if returncode == 0:
        # Check if we have any PIDs in the output
        return bool(stdout.strip())

    if returncode == 1 and not stderr.strip():
        return False

    logger.error(f"lsof error checking: returncode={returncode}, stderr={stderr.strip()}")
    return True


def file_is_open(path: Path) -> bool:
    cmd = _file_is_open_command(path)

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as error:
        logger.error(f"Failed to run lsof for {path}: {error}")
        return True

    return _file_is_open_logic_lsof(result.returncode, result.stdout.strip(), result.stderr.strip())


async def file_is_open_async(path: Path) -> bool:
    cmd = _file_is_open_command(path)

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error(f"Timeout running lsof for {path}")
            return True

    except Exception as error:
        logger.error(f"Failed to run lsof for {path}: {error}")
        return True

    return _file_is_open_logic_lsof(process.returncode, stdout.decode().strip(), stderr.decode().strip())


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
