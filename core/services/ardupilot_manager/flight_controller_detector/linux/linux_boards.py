import glob
import itertools
import os
import pathlib
import subprocess
import time
from typing import ClassVar, List, Type

import psutil
from loguru import logger
from smbus2 import SMBus
from typedefs import FlightController, PlatformType, Serial


class LinuxFlightController(FlightController):
    """Linux-based Flight-controller board."""

    NET_PATH: ClassVar[pathlib.Path] = pathlib.Path("/sys/class/net")
    ARPHRD_CAN: ClassVar[str] = "280"
    BABEL_SERIAL_GLOB: ClassVar[str] = "/dev/serial/by-id/*Babel*"
    SLCAN_SETTLE_SECONDS: ClassVar[float] = 0.2
    DETACH_TIMEOUT_SECONDS: ClassVar[float] = 3.0
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
        # Every CAN netdev reports ARPHRD_CAN, so can0, slcan0, vcan0 and any renamed bus are all found by link type
        # instead of by name.
        return sorted(
            path.parent.name for path in self.NET_PATH.glob("*/type") if path.read_text().strip() == self.ARPHRD_CAN
        )

    def slcan_interfaces(self) -> List[str]:
        # An slcan netdev has no parent device. A virtual bus has none either, so only the names slcan uses are
        # considered: slcanN before kernel 6.0, canN after.
        # ponytail: a second slcan source would also match; key on the Babel's tty if one ever ships.
        return [
            interface
            for interface in self.can_interfaces()
            if interface.startswith(("can", "slcan")) and not (self.NET_PATH / interface / "device").exists()
        ]

    def open_babel_channel(self, babel_serial: str) -> None:
        # SLCAN only takes a bitrate while the channel is closed, and the Babel needs a moment after the close before
        # it accepts one, so these three commands cannot go out in a single write. ldattach's --intro-command writes
        # them in one go, which leaves the bus at whatever rate it already had, silently: the interface comes up and
        # counts every frame the kernel hands it, while nothing on the wire is ever decoded.
        # stty's -hupcl keeps DTR asserted when this descriptor closes, so the channel stays open for ldattach.
        with open(babel_serial, "wb", buffering=0) as port:
            for command in (b"C\r", b"S8\r", b"O\r"):  # close, 1 Mbit, open
                port.write(command)
                time.sleep(self.SLCAN_SETTLE_SECONDS)

    def detach_babel(self, babel_serial: str) -> None:
        attached = [
            process
            for process in psutil.process_iter(["cmdline"])
            if (cmdline := process.info["cmdline"]) and cmdline[0] == "ldattach" and cmdline[-1] == babel_serial
        ]
        if not attached:
            return

        stale = set(self.slcan_interfaces())
        for process in attached:
            process.kill()
        # Wait for the netdev, not for the process: ldattach daemonizes, so the container's init owns it and never
        # reaps it, leaving a zombie that any process wait sits on until it times out. The descriptor closes when the
        # process dies either way, and waiting for the interface to go keeps the new one from being named around a
        # corpse, which would hand ArduPilot a port it was never configured for.
        deadline = time.monotonic() + self.DETACH_TIMEOUT_SECONDS
        while stale & set(self.can_interfaces()) and time.monotonic() < deadline:
            time.sleep(0.1)

    def attach_babel(self) -> None:
        babel_serials = sorted(glob.glob(self.BABEL_SERIAL_GLOB))
        if not babel_serials:
            return

        babel_serial = babel_serials[0]
        # The Babel is detached and reconfigured on every autopilot start, like every other CAN interface here. A
        # channel left open at another bitrate can only be fixed by closing it, and an unplugged Babel leaves its
        # ldattach holding a dead tty. ArduPilot is killed before setup runs, so dropping the interface costs nothing.
        self.detach_babel(babel_serial)

        before = set(self.can_interfaces())
        # -hupcl keeps DTR asserted when stty closes the port; the Babel drops its channel whenever DTR falls.
        subprocess.run(
            ["stty", "-F", babel_serial, "3000000", "raw", "-echo", "-hupcl", "clocal"], check=True, timeout=5
        )
        self.open_babel_channel(babel_serial)
        # Line discipline 17, N_SLCAN, which util-linux has no name for, makes the kernel turn the serial port into a
        # CAN interface. ldattach then stays in the background to hold the port.
        attach = subprocess.run(
            ["ldattach", "17", babel_serial], capture_output=True, text=True, check=False, timeout=5
        )
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
