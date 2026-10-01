import os
import pathlib
import subprocess
from typing import ClassVar, List, Type

from loguru import logger
from smbus2 import SMBus
from typedefs import FlightController, PlatformType, Serial


class LinuxFlightController(FlightController):
    """Linux-based Flight-controller board."""

    NET_PATH: ClassVar[pathlib.Path] = pathlib.Path("/sys/class/net")
    ARPHRD_CAN: ClassVar[str] = "280"
    STANDARD_SCRIPT_DIRECTORY_PATH: ClassVar[str] = "/root/.config/ardupilot-manager/firmware/scripts"
    LUA_SCRIPT_DIRECTORY_PATH: ClassVar[str] = "/shortcuts/lua_scripts"

    @property
    def type(self) -> PlatformType:
        return PlatformType.Linux

    def detect(self) -> bool:
        raise NotImplementedError

    def get_serials(self) -> List[Serial]:
        raise NotImplementedError

    def check_for_i2c_device(self, bus_number: int, address: int) -> bool:
        try:
            with SMBus(bus_number) as bus:
                bus.read_byte_data(address, 0)
            return True
        except OSError:
            return False

    def can_interfaces(self) -> List[str]:
        # Every CAN netdev reports ARPHRD_CAN, so can0, vcan0 and any renamed bus are all found by link type instead
        # of by name.
        return sorted(
            path.parent.name for path in self.NET_PATH.glob("*/type") if path.read_text().strip() == self.ARPHRD_CAN
        )

    def configure_can(self, interface: str) -> None:
        # ponytail: 1 Mbit is forced on every start, overriding host or extension setups, because ArduPilot's Linux
        # HAL ignores CAN_Pn_BITRATE. Read that parameter here if a bus ever needs another rate.
        subprocess.run(["ip", "link", "set", interface, "down"], check=True, timeout=5)
        subprocess.run(
            [
                "ip",
                "link",
                "set",
                interface,
                "up",
                "type",
                "can",
                "bitrate",
                "1000000",
                "restart-ms",
                "100",
                "loopback",
                "off",
            ],
            check=True,
            timeout=5,
        )

    def setup_can(self) -> None:
        try:
            interfaces = self.can_interfaces()
        except OSError as error:
            logger.warning(f"Failed to list CAN interfaces: {error}")
            return
        # ponytail: ArduPilot maps CAN_Pn to can(n-1), so the port order follows kernel naming at boot.
        # Rename by USB serial if a fixed mapping is ever needed.
        for interface in interfaces:
            try:
                self.configure_can(interface)
            except (OSError, subprocess.SubprocessError) as error:
                logger.warning(f"Failed to configure {interface}: {error}")

    def setup(self) -> None:
        self.setup_can()
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
