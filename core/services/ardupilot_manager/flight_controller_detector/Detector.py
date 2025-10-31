import asyncio
from typing import List, Optional

import serial
from serial import SerialException
from serial.tools.list_ports_linux import SysFS, comports
from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.general import is_running_as_root

from flight_controller_detector.bootloader.px4_bootloader import PX4BootLoader
from flight_controller_detector.linux.detector import LinuxFlightControllerDetector
from flight_controller_detector.mavlink_board_id import get_board_id
from typedefs import FlightController, FlightControllerFlags, Platform, PlatformType
from loguru import logger


class Detector:
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
    def _ask_bootloader_for_board_id_sync(port: SysFS) -> Optional[int]:
        """
        Synchronous implementation of bootloader board_id retrieval.
        Internal function - use ask_bootloader_for_board_id() instead.
        """
        try:
            logger.info(f"asking bootloader for board id on {port.device}")
            with serial.Serial(port.device, 115200, timeout=1, exclusive=True) as ser:
                bootloader = PX4BootLoader(ser)
                board_info = bootloader.get_board_info()
                return board_info.board_id
        except SerialException as e:
            logger.error(f"Error asking bootloader for board id on {port.device}: {e}")
            return None

    @staticmethod
    @temporary_cache(
        timeout_seconds=300
    )  # what are the chances of someone switching between two boards in bootloader mode?
    async def ask_bootloader_for_board_id(port: SysFS) -> Optional[int]:
        # Check if another process is already using this port
        return await asyncio.to_thread(Detector._ask_bootloader_for_board_id_sync, port)

    @staticmethod
    @temporary_cache(timeout_seconds=30)
    async def detect_serial_flight_controllers() -> List[FlightController]:
        """Check if a standalone flight controller is connected via usb/serial.

        Returns:
            List[FlightController]: List with connected serial flight controller.
        """
        sorted_serial_ports = sorted(comports(), key=lambda port: port.name)  # type: ignore
        boards = []
        for port in sorted_serial_ports:
            board_id = None
            if Detector.is_serial_bootloader(port):
                board_id = await Detector.ask_bootloader_for_board_id(port)
                # https://github.com/mavlink/qgroundcontrol/blob/f68674f47b0ca03f23a50753280516b6fa129545/src/Vehicle/VehicleSetup/FirmwareUpgradeController.cc#L43
                if board_id == 255:
                    board_id = 9  # px4_fmu-v3_default edge case
            if board_id is None:
                board_id = await get_board_id(port.device)
            if board_id is None:
                continue

            board_name = port.product or port.name
            board = FlightController(
                name=board_name,
                manufacturer=port.manufacturer,
                platform=Platform(name=board_name, platform_type=PlatformType.Serial),
                path=port.device,
                ardupilot_board_id=board_id,
                flags=[FlightControllerFlags.is_bootloader] if Detector.is_serial_bootloader(port) else [],
            )
            boards.append(board)

        # if we have multiple boards with the same name, lets keep the one with the shortest platform name
        if len(boards) > 1:
            names = [board.platform.name for board in boards]
            logger.info(f"multiple board type candidates: ({names})")

        logger.info(f"detected serial boards: {boards}")
        return boards

    @staticmethod
    def detect_sitl() -> FlightController:
        return FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL())

    @classmethod
    async def detect(cls, include_sitl: bool = True, include_manual: bool = True) -> List[FlightController]:
        """Return a list of available flight controllers

        Arguments:
            include_sitl {bool} -- To include or not SITL controllers in the returned list

        Returns:
            List[FlightController]: List of available flight controllers
        """
        available: List[FlightController] = []

        available.extend(await cls().detect_serial_flight_controllers())

        if include_sitl:
            available.append(Detector.detect_sitl())

        if include_manual:
            available.append(
                FlightController(
                    name="Manual",
                    manufacturer="Manual",
                    platform=Platform(name="Manual", platform_type=PlatformType.Serial),
                    path="",
                    ardupilot_board_id=None,
                )
            )

        if not is_running_as_root():
            return available

        linux_board = await cls.detect_linux_board()
        if linux_board:
            available.append(linux_board)

        return available
