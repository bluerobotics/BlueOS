from enum import Enum, StrEnum, auto
from platform import machine


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


class PlatformType(StrEnum):
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
