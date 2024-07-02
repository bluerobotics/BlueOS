import asyncio
from typing import List, Optional

from commonwealth.utils.general import is_running_as_root
from loguru import logger
from serial.tools.list_ports_linux import SysFS, comports
from smbus2 import SMBus

from flight_controller_detector.board_identification import identifiers
from typedefs import FlightController, FlightControllerFlags, Platform


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

        def is_navigator_r5_connected() -> bool:
            try:
                bus = SMBus(1)
                ADS1115_address = 0x48
                bus.read_byte_data(ADS1115_address, 0)

                AK09915_address = 0x0C
                bus.read_byte_data(AK09915_address, 0)

                BME280_address = 0x76
                bus.read_byte_data(BME280_address, 0)

                bus = SMBus(4)
                PCA9685_address = 0x40
                bus.read_byte_data(PCA9685_address, 0)
                return True
            except Exception as error:
                logger.warning(f"Navigator not detected: {error}")
                return False

        def is_argonot_r1_connected() -> bool:
            try:
                bus = SMBus(1)
                swap_multiplexer_address = 0x77
                bus.read_byte_data(swap_multiplexer_address, 0)
                return True
            except Exception as error:
                logger.warning(f"Argonot not detected: {error}")
                return False

        logger.debug("Trying to detect Linux board.")
        if is_navigator_r5_connected():
            logger.debug("Navigator R5 detected.")
            return FlightController(name="Navigator", manufacturer="Blue Robotics", platform=Platform.Navigator)
        if is_argonot_r1_connected():
            logger.debug("Argonot R1 detected.")
            return FlightController(name="Argonot", manufacturer="SymbyTech", platform=Platform.Argonot)
        logger.debug("No Linux board detected.")
        return None

    @staticmethod
    def is_serial_bootloader(port: SysFS) -> bool:
        return port.product is not None and "BL" in port.product

    @staticmethod
    def detect_serial_platform(port: SysFS) -> Optional[Platform]:
        for identifier in identifiers:
            port_attr = getattr(port, identifier.attribute)
            if port_attr is not None and identifier.id_value in port_attr:
                return identifier.platform

        return None

    @staticmethod
    def detect_serial_flight_controllers() -> List[FlightController]:
        """Check if a Pixhawk1 or a Pixhawk4 is connected.

        Returns:
            List[FlightController]: List with connected serial flight controller.
        """
        sorted_serial_ports = sorted(comports(), key=lambda port: port.name)  # type: ignore
        unique_serial_devices: List[SysFS] = []
        for port in sorted_serial_ports:
            # usb_device_path property will be the same for two serial connections using the same USB port
            if (port.usb_device_path or port.name) not in [
                (device.usb_device_path or device.name) for device in unique_serial_devices
            ]:
                unique_serial_devices.append(port)
        boards = [
            FlightController(
                name=port.product or port.name,
                manufacturer=port.manufacturer,
                platform=Detector.detect_serial_platform(port)
                or Platform(),  # this is just to make CI happy. check line 82
                path=port.device,
            )
            for port in unique_serial_devices
            if Detector.detect_serial_platform(port) is not None
        ]
        for port in unique_serial_devices:
            for board in boards:
                if board.path == port.device and Detector.is_serial_bootloader(port):
                    board.flags.append(FlightControllerFlags.is_bootloader)
        return boards

    @staticmethod
    def detect_sitl() -> FlightController:
        return FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)

    @classmethod
    async def detect(cls, include_sitl: bool = True) -> List[FlightController]:
        """Return a list of available flight controllers

        Arguments:
            include_sitl {bool} -- To include or not SITL controllers in the returned list

        Returns:
            List[FlightController]: List of available flight controllers
        """
        available: List[FlightController] = []
        if not is_running_as_root():
            return available

        linux_board = await cls.detect_linux_board()
        if linux_board:
            available.append(linux_board)

        available.extend(cls().detect_serial_flight_controllers())

        if include_sitl:
            available.append(Detector.detect_sitl())

        return available
