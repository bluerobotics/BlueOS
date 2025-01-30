from flight_controller import Platform
from flight_controller.detector.linux.navigator import NavigatorPi4


class Argonot(NavigatorPi4):
    name = "Argonot"
    manufacturer = "SymbyTech"
    platform = Platform.Argonot

    devices = {
        "swap_multiplexer": (0x77, 1),
    }
