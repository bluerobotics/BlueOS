import glob
import itertools
import os
import pathlib
import subprocess
from typing import ClassVar, List, Type

import psutil
from loguru import logger
from smbus2 import SMBus
from typedefs import FlightController, PlatformType, Serial


class LinuxFlightController(FlightController):
    """Linux-based Flight-controller board."""

    NET_PATH: ClassVar[pathlib.Path] = pathlib.Path("/sys/class/net")
    BABEL_SERIAL_GLOB: ClassVar[str] = "/dev/serial/by-id/*Babel*"
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
        return sorted(path.name for path in self.NET_PATH.iterdir() if path.name.startswith(("can", "slcan")))

    def attach_babel(self) -> None:
        babel_serials = sorted(glob.glob(self.BABEL_SERIAL_GLOB))
        if not babel_serials:
            return

        babel_serial = babel_serials[0]
        # ldattach sets the port's tty line discipline to 17, N_SLCAN, which util-linux has no name for. That discipline
        # makes the kernel turn the serial port into a CAN interface. Before attaching, -c sends the Babel the SLCAN
        # commands C (close channel), S8 (1 Mbit) and O (open channel) from ldattach's own descriptor, which stays open,
        # so the port never closes between configuring the Babel and attaching it. Use -c rather than --intro-command,
        # which util-linux 2.38 declares without an argument. ldattach then stays in the background to hold the port.
        command = ["ldattach", "-c", "C\rS8\rO\r", "17", babel_serial]
        # An unplugged Babel leaves its ldattach holding the dead tty. ldattach rewrites the \r in its -c argument to \n,
        # so match on the program and port only.
        for process in psutil.process_iter(["cmdline"]):
            cmdline = process.info["cmdline"]
            if cmdline and cmdline[0] == "ldattach" and cmdline[-1] == babel_serial:
                process.kill()

        before = set(self.can_interfaces())
        # -hupcl keeps DTR asserted when stty closes the port; the Babel drops its channel whenever DTR falls.
        subprocess.run(
            ["stty", "-F", babel_serial, "3000000", "raw", "-echo", "-hupcl", "clocal"], check=True, timeout=5
        )
        attach = subprocess.run(command, capture_output=True, text=True, check=False, timeout=5)
        if attach.returncode != 0:
            raise RuntimeError(f"ldattach failed: {attach.stderr.strip()}")
        # The kernel creates the interface while ldattach sets the discipline, before ldattach daemonizes.
        if not set(self.can_interfaces()) - before:
            raise RuntimeError("SLCAN interface did not appear")
        logger.info("Attached BabelCAN.")

    def configure_can(self, interface: str) -> None:
        if interface.startswith("slcan"):
            # Kernels before 6.0 name slcan netdevs slcanN, but ArduPilot only opens canN.
            taken = set(self.can_interfaces())
            name = next(f"can{index}" for index in itertools.count() if f"can{index}" not in taken)
            subprocess.run(["ip", "link", "set", interface, "name", name], check=True, timeout=5)
            interface = name
        # slcan netdevs have no parent device. They reject restart-ms, and kernels before 6.0 reject any bitrate,
        # so the Babel gets its bitrate from the ldattach intro instead.
        if not (self.NET_PATH / interface / "device").exists():
            subprocess.run(["ip", "link", "set", interface, "up"], check=True, timeout=5)
            return
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
            # The Babel is the only slcan source, so an interface without a parent device means it is already attached.
            # ponytail: a second slcan source would also match; key on the Babel's tty if one ever ships.
            if all((self.NET_PATH / interface / "device").exists() for interface in self.can_interfaces()):
                self.attach_babel()
        except (OSError, RuntimeError, subprocess.SubprocessError, psutil.Error) as error:
            logger.warning(f"Failed to attach BabelCAN: {error}")

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
