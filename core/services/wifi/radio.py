import asyncio
from pathlib import Path
from typing import List

from loguru import logger
from typedefs import RfkillStatus

RFKILL_PATH = Path("/sys/class/rfkill")


def _wlan_devices() -> List[Path]:
    devices = []
    for device in RFKILL_PATH.glob("rfkill*"):
        try:
            if (device / "type").read_text().strip() == "wlan":
                devices.append(device)
        except OSError:
            # Hotplugged away between the glob and the read
            continue
    return devices


def _read_flag(device: Path, attribute: str) -> bool:
    try:
        return (device / attribute).read_text().strip() == "1"
    except OSError:
        return False


def _rfkill_status() -> RfkillStatus:
    devices = _wlan_devices()
    return RfkillStatus(
        soft_blocked=any(_read_flag(device, "soft") for device in devices),
        hard_blocked=any(_read_flag(device, "hard") for device in devices),
    )


def _rfkill_unblock() -> None:
    for device in _wlan_devices():
        try:
            (device / "soft").write_text("0")
        except OSError as error:
            logger.warning(f"Could not unblock {device.name}: {error}")


async def rfkill_status() -> RfkillStatus:
    # The core container is privileged and binds /sys, so the kernel state is read directly instead of going
    # through a host command
    return await asyncio.to_thread(_rfkill_status)


async def rfkill_unblock() -> None:
    await asyncio.to_thread(_rfkill_unblock)
