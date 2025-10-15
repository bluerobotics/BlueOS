from flight_controller_detector.linux.navigator import NavigatorPi4
from typedefs import Platform, PlatformType


class Argonot(NavigatorPi4):
    name = "Argonot"
    manufacturer = "SymbyTech"
    platform = Platform(name="Argonot", platform_type=PlatformType.Linux)

    devices = {
        "swap_multiplexer": (0x77, 1),
    }
