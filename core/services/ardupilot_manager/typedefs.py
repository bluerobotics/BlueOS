from enum import Enum, IntEnum
from platform import machine

from pydantic import BaseModel, HttpUrl


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


def get_sitl_platform_name() -> str:
    if machine() == "x86_64":
        return "SITL_x86_64_linux_gnu"
    return "SITL_arm_linux_gnueabihf"


class Firmware(BaseModel):
    name: str
    url: HttpUrl


class Vehicle(str, Enum):
    """Valid vehicle types to download"""

    Sub = "Sub"
    Rover = "Rover"
    Plane = "Plane"
    Copter = "Copter"


class Platform(str, Enum):
    """Valid platform types to download
    The Enum values are 1:1 representations of the platforms available on the ArduPilot manifest."""

    Pixhawk1 = "Pixhawk1"
    Navigator = "navigator"
    SITL = get_sitl_platform_name()
    Undefined = "Undefined"


class FirmwareFormat(str, Enum):
    """Valid firmware formats to download.
    The Enum values are 1:1 representations of the formats available on the ArduPilot manifest."""

    APJ = "apj"
    ELF = "ELF"


class FlightControllerType(IntEnum):
    Serial = 1
    NavigatorR3 = 2
    NavigatorR4 = 3


class EndpointType(str, Enum):
    UDPServer = "udpin"
    UDPClient = "udpout"
    TCPServer = "tcpin"
    TCPClient = "tcpout"
    Serial = "serial"
