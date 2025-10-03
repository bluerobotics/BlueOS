import asyncio
from typing import List, Optional

import serial


from commonwealth.utils.decorators import temporary_cache
from commonwealth.utils.general import is_running_as_root
from serial.tools.list_ports_linux import SysFS, comports

from flight_controller_detector.bootloader.px4_bootloader import PX4BootLoader
from flight_controller_detector.board_identification import load_board_identifiers
from flight_controller_detector.linux.detector import LinuxFlightControllerDetector
from flight_controller_detector.port_checker import is_port_in_use
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

    # todo: cache this
    @staticmethod
    def detect_serial_platform(port: SysFS) -> list[Platform]:
        """
        Detect the platform of a serial flight controller.
        Returns a list of platforms that the board could be.
        Tries to talk to the bootloader first, if that fails,
        it will use the USB VID:PID to identify the board.
        """
        vid = port.vid
        pid = port.pid

        # Check if vid and pid are not None before formatting
        if vid is None or pid is None:
            return []

        usb_id = f"{vid:04x}:{pid:04x}"
        platforms = []

        board_id = None
        if Detector.is_serial_bootloader(port):
            board_id = Detector.ask_bootloader_for_board_id(port)
            # https://github.com/mavlink/qgroundcontrol/blob/f68674f47b0ca03f23a50753280516b6fa129545/src/Vehicle/VehicleSetup/FirmwareUpgradeController.cc#L43
            if board_id == 255:
                board_id = 9  # px4_fmu-v3_default edge case
        identifiers = load_board_identifiers()

        if usb_id in identifiers:
            for board_platform in identifiers[usb_id]:
                if board_id is None or board_id == identifiers[usb_id][board_platform]:
                    logger.info(f"detected board {board_platform} with id {identifiers[usb_id][board_platform]}")
                    platforms.append(
                        Platform(
                            name=board_platform,
                            platform_type=PlatformType.Serial,
                            board_id=identifiers[usb_id][board_platform],
                        )
                    )
        return platforms

    @staticmethod
    @temporary_cache(
        timeout_seconds=300
    )  # what are the chances of someone switching between two boards in bootloader mode?
    def ask_bootloader_for_board_id(port: SysFS) -> Optional[int]:
        # Check if another process is already using this port
        if is_port_in_use(port.device):
            logger.warning(f"Port {port.device} is already in use, skipping")
            return None
        logger.info(f"asking bootloader for board id on {port.device}")
        with serial.Serial(port.device, 115200, timeout=1) as ser:
            bootloader = PX4BootLoader(ser)
            board_info = bootloader.get_board_info()
            return board_info.board_id

    @staticmethod
    @temporary_cache(timeout_seconds=30)
    def detect_serial_flight_controllers() -> List[FlightController]:
        """Check if a standalone flight controller is connected via usb/serial.

        Returns:
            List[FlightController]: List with connected serial flight controller.
        """
        sorted_serial_ports = sorted(comports(), key=lambda port: port.name)  # type: ignore
        unique_serial_devices: List[SysFS] = []
        for port in sorted_serial_ports:
            # usb_device_path property will be the same for two serial connections using the same USB port
            if port.usb_device_path not in [device.usb_device_path for device in unique_serial_devices]:
                unique_serial_devices.append(port)

        boards = []
        for port in unique_serial_devices:
            platforms = Detector.detect_serial_platform(port)
            for platform in platforms:
                board_name = port.product or port.name
                board_id = platform.board_id
                board = FlightController(
                    name=board_name + f" ({platform.name})",
                    manufacturer=port.manufacturer,
                    platform=platform,
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

        available.extend(cls().detect_serial_flight_controllers())

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
