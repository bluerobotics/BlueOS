import ipaddress
from platform import machine
import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, validator


class SITLFrame(str, Enum):
    """Valid SITL frame types"""

    QUADPLANE = "quadplane"
    XPLANE = "xplane"
    FIREFLY = "firefly"
    PLUS_CONFIG = "+"
    QUAD = "quad"
    COPTER = "copter"
    X_CONFIG = "x"
    BFXREV = "bfxrev"
    BFX = "bfx"
    DJIX = "djix"
    CWX = "cwx"
    HEXA = "hexa"
    HEXA_CWX = "hexa-cwx"
    HEXA_DJI = "hexa-dji"
    OCTA = "octa"
    OCTA_CWX = "octa-cwx"
    OCTA_DJI = "octa-dji"
    OCTA_QUAD_CWX = "octa-quad-cwx"
    DODECA_HEXA = "dodeca-hexa"
    TRI = "tri"
    Y_SIX = "y6"
    HELI = "heli"
    HELI_DUAL = "heli-dual"
    HELI_COMPOUND = "heli-compound"
    SINGLECOPTER = "singlecopter"
    COAXCOPTER = "coaxcopter"
    ROVER = "rover"
    BALANCEBOT = "balancebot"
    SAILBOAT = "sailboat"
    MOTORBOAT = "motorboat"
    CRRCSIM = "crrcsim"
    JSBSIM = "jsbsim"
    FLIGHTAXIS = "flightaxis"
    GAZEBO = "gazebo"
    LAST_LETTER = "last_letter"
    TRACKER = "tracker"
    BALLOON = "balloon"
    PLANE = "plane"
    CALIBRATION = "calibration"
    VECTORED = "vectored"
    VECTORED_6DOF = "vectored_6dof"
    SILENTWINGS = "silentwings"
    MORSE = "morse"
    AIRSIM = "airsim"
    SCRIMMAGE = "scrimmage"
    WEBOTS = "webots"
    JSON = "JSON"
    UNDEFINED = "undefined"


def get_sitl_platform_name(machine_arch: str) -> str:
    """Get SITL platform name based on machine architecture."""

    if "arm" not in machine_arch.lower() and "aarch" not in machine_arch.lower():
        return "SITL_x86_64_linux_gnu"
    return "SITL_arm_linux_gnueabihf"


class Firmware(BaseModel):
    """Simplified representation of a firmware, as available on Ardupilot's manifest."""

    board_id: Optional[int]
    platform: str
    name: str
    url: str

    def __hash__(self) -> int:
        return hash(self.platform + self.name + str(self.board_id))


class Vehicle(str, Enum):
    """Valid Ardupilot vehicle types.
    The Enum values are 1:1 representations of the vehicles available on the ArduPilot manifest."""

    Sub = "Sub"
    Rover = "Rover"
    Plane = "Plane"
    Copter = "Copter"


class PlatformType(str, Enum):
    Serial = "Serial"
    Linux = "Linux"
    SITL = "SITL"
    Unknown = "Unknown"
    Manual = "Manual"


class Platform(BaseModel):
    """Valid Ardupilot platform types.
    The Names are a 1:1 representation of the platforms available on the ArduPilot manifest."""

    name: str
    platform_type: PlatformType

    @staticmethod
    def SITL() -> "Platform":
        return Platform(name=get_sitl_platform_name(machine()), platform_type=PlatformType.SITL)


class FlightControllerFlags(str, Enum):
    """Flags for the Flight-controller class."""

    is_bootloader = "is_bootloader"


class Parameters(BaseModel):
    params: Dict[str, float]


class FlightController(BaseModel):
    """Flight-controller board."""

    name: str  # Whatever we get on the usb description
    manufacturer: Optional[str]  # Whatever we get on the usb description
    platform: Platform  # The platform of the board according to the ardupilot's manifest.
    ardupilot_board_id: Optional[int]
    path: Optional[str]
    flags: List[FlightControllerFlags] = []

    @property
    def type(self) -> PlatformType:
        return self.platform.platform_type

    def __hash__(self) -> int:
        return hash(self.name + self.platform.name)


class FlightControllerV1(BaseModel):
    """Flight-controller board."""

    name: str  # Whatever we get on the usb description
    manufacturer: Optional[str]  # Whatever we get on the usb description
    platform: str  # The platform of the board according to the ardupilot's manifest.
    ardupilot_board_id: Optional[int]
    path: Optional[str]
    flags: List[FlightControllerFlags] = []


class AvailableBoards(BaseModel):
    regular: List[FlightController]
    bootloaders: List[FlightController]


class FirmwareFormat(str, Enum):
    """Valid firmware formats.
    The Enum values are 1:1 representations of the formats available on the ArduPilot manifest."""

    APJ = "apj"
    ELF = "ELF"


class Serial(BaseModel):
    """Simplified representation of linux serial port configurations,
    gets transformed into command line arguments such as
    --serial1 /dev/ttyS0
    --serial3 /dev/ttyAMA1
    --serial4 /dev/ttyAMA2
    --serial5 /dev/ttyAMA3
    """

    port: str
    endpoint: str

    @validator("port")
    @classmethod
    def valid_letter(cls: Any, value: str) -> str:
        if value in "BCDEFGH" and len(value) == 1:
            return value
        raise ValueError(f"Invalid serial port: {value}. These must be between B and H. A is reserved.")

    @validator("endpoint")
    @classmethod
    def valid_endpoint(cls: Any, value: str) -> str:
        if Path(value).exists():
            return value
        if re.compile(r"tcp:\d*:wait$").match(value):
            return value
        matches = re.compile(r"(tcpclient|udp|tcpin|udpin):(?P<ip>(\d*\.){3}\d+):(?P<port>\d*)$").match(value)
        if matches:
            ipaddress.ip_address(matches.group("ip"))
            if 0 <= int(matches.group("port")) <= 65535:
                return value
        raise ValueError(f"Invalid endpoint configuration: {value}")

    def __hash__(self) -> int:  # make hashable BaseModel subclass
        return hash(self.port + self.endpoint)
