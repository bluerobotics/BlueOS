from enum import StrEnum
from typing import List, Optional

from pydantic import BaseModel, Field


class ArdupilotFirmwareFormats(StrEnum):
    apj = "apj"
    hex = "hex"
    px4 = "px4"
    elf = "ELF"
    ELF = "ELF"
    bin = "bin"
    abin = "abin"


class ArdupilotVehicleTypes(StrEnum):
    blimp = "Blimp"
    plane = "Plane"
    sub = "Sub"
    ap_periph = "AP_Periph"
    copter = "Copter"
    rover = "Rover"
    antenna_tracker = "AntennaTracker"


class ArdupilotManifestEntry(BaseModel):
    mav_autopilot: str = Field(default="ARDUPILOTMEGA", alias="mav-autopilot")
    vehicletype: ArdupilotVehicleTypes = Field(alias="vehicletype")
    platform: str = Field(alias="platform")

    git_sha: str = Field(alias="git-sha")
    url: str = Field(alias="url")

    mav_type: str = Field(alias="mav-type")
    latest: int = Field(alias="latest")
    format: ArdupilotFirmwareFormats = Field(alias="format")

    mav_firmware_version: str = Field(alias="mav-firmware-version")
    mav_firmware_version_str: str = Field(alias="mav-firmware-version-str")
    mav_firmware_version_type: str = Field(alias="mav-firmware-version-type")
    mav_firmware_version_major: str = Field(alias="mav-firmware-version-major")
    mav_firmware_version_minor: str = Field(alias="mav-firmware-version-minor")
    mav_firmware_version_patch: str = Field(alias="mav-firmware-version-patch")

    manufacturer: Optional[str] = Field(default=None)
    board_id: Optional[str] = Field(default=None)
    bootloader_str: Optional[List[str]] = Field(default=None)
    usb_id: Optional[List[str]] = Field(default=None, alias="USBID")
    brand_name: Optional[str] = Field(default=None)
    image_size: Optional[int] = Field(default=None)


class ArdupilotManifestData(BaseModel):
    format_version: str = Field(alias="format-version")
    firmware: List[ArdupilotManifestEntry] = Field(default_factory=list)
