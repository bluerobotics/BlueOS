from enum import Enum

from pydantic import BaseModel


class FirmwareVersionType(str, Enum):
    DEV = "DEV"
    ALPHA = "ALPHA"
    BETA = "BETA"
    RC = "RC"
    STABLE = "STABLE"

    @staticmethod
    def from_value(firmware_value: int) -> "FirmwareVersionType":
        return {
            0: FirmwareVersionType.DEV,
            64: FirmwareVersionType.ALPHA,
            128: FirmwareVersionType.BETA,
            192: FirmwareVersionType.RC,
            255: FirmwareVersionType.STABLE,
        }[firmware_value]


class FirmwareInfo(BaseModel):
    version: str
    type: FirmwareVersionType


class MavlinkMessageId(Enum):
    HEARTBEAT = 0
    AUTOPILOT_VERSION = 148
