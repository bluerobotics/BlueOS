from loguru import logger
from smbus2 import SMBus

from flight_controller_detector.linux.linux_boards.navigator import Navigator
from typedefs import Platform


class Argonot(Navigator):
    name = "Argonot"
    manufacturer = "SymbyTech"
    platform = Platform.Argonot

    def detect(self):
        try:
            bus = SMBus(1)
            swap_multiplexer_address = 0x77
            bus.read_byte_data(swap_multiplexer_address, 0)
            return True
        except Exception as error:
            logger.warning(f"Argonot not detected: {error}")
            return False
