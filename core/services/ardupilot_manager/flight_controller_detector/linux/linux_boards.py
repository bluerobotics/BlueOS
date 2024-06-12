from typing import List, Optional

from loguru import logger
from smbus2 import SMBus

from typedefs import FlightController, PlatformType, Serial


class LinuxFlightController(FlightController):
    """Linux-based Flight-controller board."""

    # for sanity reasons, let's assume a linux board never gets disconnected
    # this will prevent a lot of loading/unloading of modules and overlays
    previously_detected: Optional[FlightController] = None

    @property
    def type(self) -> PlatformType:
        return PlatformType.Linux

    def detect(self):
        raise NotImplementedError

    def serial_ports_mapping(self):
        raise NotImplementedError

    def get_serial_cmdlines(self) -> str:
        cmdlines = [f"-{entry.port} {entry.endpoint}" for entry in self.get_serials()]
        return " ".join(cmdlines)

    def get_serials(self) -> List[Serial]:
        raise NotImplementedError

    @staticmethod
    def setup_board():
        # loads overlays and required modules in runtime
        raise NotImplementedError

    def check_for_i2c_device(self, bus, address) -> bool:
        try:
            bus = SMBus(bus)
            bus.read_byte_data(address, 0)
            return True
        except OSError:
            return False

    @classmethod
    def detect_boards(cls, ignore_cache: bool = False) -> Optional["LinuxFlightController"]:
        from flight_controller_detector.linux.navigator import (
            NavigatorPi4,
            NavigatorPi5,
        )

        if not hasattr(cls, "previously_detected"):
            cls.previously_detected = None
        if cls.previously_detected and not ignore_cache:
            return cls.previously_detected
        for candidate in [NavigatorPi4, NavigatorPi5]:
            logger.info(f"Detecting Linux board: {candidate.__name__}")
            if candidate().detect():
                logger.info(f"Detected Linux board: {candidate.__name__}")
                cls.previously_detected = candidate()
                return candidate()
        raise RuntimeError("No Linux board detected")
