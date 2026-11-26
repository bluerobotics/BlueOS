import asyncio
import time
from typing import Dict, List, Optional, Sequence, Tuple

import serial
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.general import is_running_as_root
from flight_controller_detector.bootloader.px4_bootloader import PX4BootLoader
from flight_controller_detector.linux.detector import LinuxFlightControllerDetector
from flight_controller_detector.mavlink_board_id import get_board_id
from flight_controller_detector.serial_identification import (
    is_plausible_autopilot,
    is_usb_port,
    serial_platform_name,
)
from loguru import logger
from serial.tools.list_ports_linux import SysFS, comports
from typedefs import FlightController, FlightControllerFlags, Platform, PlatformType

BOOTLOADER_CACHE_SECONDS = 60


class Detector:
    # (device, USB serial number) -> (time of the probe, board id)
    _bootloader_cache: Dict[Tuple[str, Optional[str]], Tuple[float, int]] = {}

    @classmethod
    async def detect_linux_board(cls) -> Optional[FlightController]:
        for _i in range(5):
            board = cls._detect_linux_board()
            if board:
                return board
            await asyncio.sleep(0.1)
        return None

    @classmethod
    def _detect_linux_board(cls) -> Optional[FlightController]:
        """Returns Linux board if connected.
        Check for connection using the sensors on the I²C and SPI buses.

        Returns:
            Optional[FlightController]: Return FlightController if connected, None otherwise.
        """
        return LinuxFlightControllerDetector.detect_boards()

    @staticmethod
    def is_serial_bootloader(port: SysFS) -> bool:
        return port.product is not None and "BL" in port.product

    @staticmethod
    def _ask_bootloader_for_board_id_sync(device: str) -> Optional[int]:
        """
        Synchronous implementation of bootloader board_id retrieval.
        Internal function - use ask_bootloader_for_board_id() instead.
        """
        try:
            logger.info(f"asking bootloader for board id on {device}")
            with serial.Serial(device, 115200, timeout=0.2, write_timeout=0, exclusive=True) as ser:
                bootloader = PX4BootLoader(ser)
                try:
                    return bootloader.get_board_info().board_id
                finally:
                    bootloader.boot()
        except Exception as error:
            # Any device with "BL" on its product name lands here, the probe must never break the detection
            logger.warning(f"Error asking bootloader for board id on {device}: {error}")
            return None

    @classmethod
    async def ask_bootloader_for_board_id(cls, port: SysFS) -> Optional[int]:
        key = (port.device, port.serial_number)
        cached = cls._bootloader_cache.get(key)
        if cached is not None and time.monotonic() - cached[0] < BOOTLOADER_CACHE_SECONDS:
            return cached[1]
        board_id = await asyncio.to_thread(cls._ask_bootloader_for_board_id_sync, port.device)
        if board_id is not None:
            cls._bootloader_cache[key] = (time.monotonic(), board_id)
        return board_id

    @staticmethod
    def _usb_interface_number(port: SysFS) -> int:
        # location looks like "1-1.2:1.0", the number after the last dot is the USB interface
        try:
            return int(port.location.rsplit(".", 1)[1])
        except (AttributeError, IndexError, ValueError):
            return 0

    @staticmethod
    async def _detect_serial_port(port: SysFS, known_boards: Sequence[FlightController]) -> Optional[FlightController]:
        if not is_plausible_autopilot(port):
            return None

        is_bootloader = Detector.is_serial_bootloader(port)
        if not is_bootloader:
            # The running board's port is held exclusively by the router, probing it would fail
            known_board = next((board for board in known_boards if board.path == port.device), None)
            if known_board is not None:
                return known_board

        board_id = None
        if is_bootloader:
            board_id = await Detector.ask_bootloader_for_board_id(port)
            # https://github.com/mavlink/qgroundcontrol/blob/f68674f47b0ca03f23a50753280516b6fa129545/src/Vehicle/VehicleSetup/FirmwareUpgradeController.cc#L43
            if board_id == 255:
                board_id = 9  # px4_fmu-v3_default edge case
        if board_id is None:
            board_id = await get_board_id(port.device)
        if board_id is None:
            return None

        return FlightController(
            name=port.product or port.name,
            manufacturer=port.manufacturer,
            platform=Platform(name=serial_platform_name(port.product), platform_type=PlatformType.Serial),
            path=port.device,
            ardupilot_board_id=board_id,
            flags=[FlightControllerFlags.is_bootloader] if is_bootloader else [],
        )

    @staticmethod
    @temporary_cache(timeout_seconds=5)
    async def detect_serial_flight_controllers(
        known_boards: Tuple[FlightController, ...] = (),
    ) -> List[FlightController]:
        """Check if a standalone flight controller is connected via USB.

        Arguments:
            known_boards: Boards already in use, reused without probing when their port is still present.

        Returns:
            List[FlightController]: List with connected serial flight controller.
        """
        usb_devices: Dict[str, List[SysFS]] = {}
        for port in comports():
            if is_usb_port(port):
                # usb_device_path property will be the same for two serial connections using the same USB port
                usb_devices.setdefault(port.usb_device_path, []).append(port)

        boards = []
        for ports in sorted(usb_devices.values(), key=lambda ports: min(port.name for port in ports)):
            for port in sorted(ports, key=lambda port: (Detector._usb_interface_number(port), port.name)):
                board = await Detector._detect_serial_port(port, known_boards)
                if board is not None:
                    boards.append(board)
                    break

        logger.debug(f"detected serial boards: {boards}")
        return boards

    @classmethod
    def invalidate_caches(cls) -> None:
        cls.detect_serial_flight_controllers.invalidate()  # type: ignore[attr-defined]
        cls._bootloader_cache.clear()

    @staticmethod
    def detect_sitl() -> FlightController:
        return FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL())

    @staticmethod
    def detect_manual() -> FlightController:
        return FlightController(
            name="Manual", manufacturer="Manual", platform=Platform(name="Manual", platform_type=PlatformType.Manual)
        )

    @classmethod
    async def detect(
        cls,
        include_sitl: bool = True,
        include_manual: bool = True,
        known_boards: Optional[Sequence[FlightController]] = None,
    ) -> List[FlightController]:
        """Return a list of available flight controllers

        Arguments:
            include_sitl {bool} -- To include or not SITL controllers in the returned list
            known_boards -- Serial boards already in use, see detect_serial_flight_controllers

        Returns:
            List[FlightController]: List of available flight controllers
        """
        available: List[FlightController] = []

        available.extend(await cls.detect_serial_flight_controllers(tuple(known_boards or ())))

        if include_sitl:
            available.append(Detector.detect_sitl())

        if include_manual:
            available.append(Detector.detect_manual())

        if not is_running_as_root():
            return available

        linux_board = await cls.detect_linux_board()
        if linux_board:
            available.append(linux_board)

        return available
