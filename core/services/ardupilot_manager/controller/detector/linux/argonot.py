from controller.detector.linux.navigator import NavigatorPi4
from controller.platform import Platform


class Argonot(NavigatorPi4):
    name = "Argonot"
    manufacturer = "SymbyTech"
    platform = Platform.Argonot

    devices = {
        "swap_multiplexer": (0x77, 1),
    }
