from flight_controller_detector.linux.navigator import NavigatorPi4
from typedefs import Platform


class Placeholder(NavigatorPi4):
    name = "Placeholder"
    manufacturer = "JWeston"
    platform = Platform.Placeholder

    devices = {
        "swap_multiplexer": (0x77, 1),
    }