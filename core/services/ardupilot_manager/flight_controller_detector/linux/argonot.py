from typing import Any, ClassVar, Dict, Tuple

from flight_controller_detector.linux.navigator import NavigatorPi4
from typedefs import Platform, PlatformType


class Argonot(NavigatorPi4):
    devices: ClassVar[Dict[str, Tuple[int, int]]] = {
        "swap_multiplexer": (0x77, 1),
    }

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # Navigator.__init__ always labels the board as Navigator. Restore Argonot identity.
        self.name = "Argonot"
        self.manufacturer = "SymbyTech"
        self.platform = Platform(name="Argonot", platform_type=PlatformType.Linux)
