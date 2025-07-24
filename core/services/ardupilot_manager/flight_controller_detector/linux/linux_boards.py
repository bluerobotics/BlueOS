import os
from typing import List, Type

from smbus2 import SMBus

from typedefs import FlightController, PlatformType, Serial


class LinuxFlightController(FlightController):
    """Linux-based Flight-controller board."""

    STANDARD_SCRIPT_DIRECTORY_PATH = "/root/.config/ardupilot-manager/firmware/scripts"
    LUA_SCRIPT_DIRECTORY_PATH = "/shortcuts/lua_scripts"

    @property
    def type(self) -> PlatformType:
        return PlatformType.Linux

    def detect(self) -> bool:
        raise NotImplementedError

    def get_serials(self) -> List[Serial]:
        raise NotImplementedError

    def check_for_i2c_device(self, bus_number: int, address: int) -> bool:
        try:
            bus = SMBus(bus_number)
            bus.read_byte_data(address, 0)
            return True
        except OSError:
            return False

    def setup(self) -> None:
        os.makedirs(self.STANDARD_SCRIPT_DIRECTORY_PATH, exist_ok=True)
        try:
            os.symlink(self.STANDARD_SCRIPT_DIRECTORY_PATH, self.LUA_SCRIPT_DIRECTORY_PATH)
        except FileExistsError:
            pass

    @classmethod
    def get_all_boards(cls) -> List[Type["LinuxFlightController"]]:
        all_subclasses = []

        for subclass in cls.__subclasses__():
            all_subclasses.append(subclass)
            all_subclasses.extend(subclass.get_all_boards())

        return all_subclasses
