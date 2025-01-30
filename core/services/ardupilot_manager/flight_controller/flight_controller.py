from enum import Enum, auto
from platform import machine
from typing import List, Optional

from pydantic import BaseModel


def get_sitl_platform_name(machine_arch: str) -> str:
    """Get SITL platform name based on machine architecture."""

    if "arm" not in machine_arch.lower() and "aarch" not in machine_arch.lower():
        return "SITL_x86_64_linux_gnu"
    return "SITL_arm_linux_gnueabihf"


# TODO: This class can be deprecated once we move to Python 3.11, which introduces the equivalent StrEnum
class LowerStringEnum(str, Enum):
    def __str__(self) -> str:
        return self.name.lower()


class PlatformType(LowerStringEnum):
    Serial = auto()
    Linux = auto()
    SITL = auto()
    Unknown = auto()


class Platform(str, Enum):
    """Valid Ardupilot platform types.
    The Enum values are 1:1 representations of the platforms available on the ArduPilot manifest."""

    Pixhawk1 = "Pixhawk1"
    Pixhawk4 = "Pixhawk4"
    Pixhawk6X = "Pixhawk6X"
    Pixhawk6C = "Pixhawk6C"
    CubeOrange = "CubeOrange"
    GenericSerial = "GenericSerial"
    Navigator = "navigator"
    Argonot = "argonot"
    SITL = get_sitl_platform_name(machine())

    @property
    def type(self) -> PlatformType:
        platform_types = {
            Platform.Pixhawk1: PlatformType.Serial,
            Platform.Pixhawk4: PlatformType.Serial,
            Platform.Pixhawk6X: PlatformType.Serial,
            Platform.Pixhawk6C: PlatformType.Serial,
            Platform.CubeOrange: PlatformType.Serial,
            Platform.GenericSerial: PlatformType.Serial,
            Platform.Navigator: PlatformType.Linux,
            Platform.Argonot: PlatformType.Linux,
            Platform.SITL: PlatformType.SITL,
        }
        return platform_types.get(self, PlatformType.Unknown)


class FlightControllerFlags(str, Enum):
    """Flags for the Flight-controller class."""

    is_bootloader = "is_bootloader"


class FlightController(BaseModel):
    """Flight-controller board."""

    name: str
    manufacturer: Optional[str]
    platform: Platform
    path: Optional[str]
    flags: List[FlightControllerFlags] = []

    @property
    def type(self) -> PlatformType:
        return self.platform.type
