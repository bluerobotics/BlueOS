from typing import ClassVar, Dict, Optional, Tuple

from flight_controller_detector.linux.navigator import NavigatorPi4
from typedefs import Platform


class Argonot(NavigatorPi4):
    name: str = "Argonot"
    manufacturer: Optional[str] = "SymbyTech"
    platform: Platform = Platform.Argonot

    devices: ClassVar[Dict[str, Tuple[int, int]]] = {
        "swap_multiplexer": (0x77, 1),
    }
