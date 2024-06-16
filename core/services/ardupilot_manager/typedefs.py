import ipaddress
import re
from enum import Enum, auto
from pathlib import Path
from platform import machine
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
    JSON = " JSON"
    UNDEFINED = " undefined"


def get_sitl_platform_name(machine_arch: str) -> str:
    """Get SITL platform name based on machine architecture."""

    if "arm" not in machine_arch.lower() and "aarch" not in machine_arch.lower():
        return "SITL_x86_64_linux_gnu"
    return "SITL_arm_linux_gnueabihf"


class Firmware(BaseModel):
    """Simplified representation of a firmware, as available on Ardupilot's manifest."""

    name: str
    url: str


class Vehicle(str, Enum):
    """Valid Ardupilot vehicle types.
    The Enum values are 1:1 representations of the vehicles available on the ArduPilot manifest."""

    Sub = "Sub"
    Rover = "Rover"
    Plane = "Plane"
    Copter = "Copter"


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


class Parameters(BaseModel):
    params: Dict[str, float]


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


class AvailableBoards(BaseModel):
    regular: List[FlightController]
    bootloaders: List[FlightController]


class FirmwareFormat(str, Enum):
    """Valid firmware formats.
    The Enum values are 1:1 representations of the formats available on the ArduPilot manifest."""

    APJ = "apj"
    ELF = "ELF"


class EndpointType(str, Enum):
    """Supported Mavlink endpoint types."""

    UDPServer = "udpin"
    UDPClient = "udpout"
    TCPServer = "tcpin"
    TCPClient = "tcpout"
    Serial = "serial"


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
