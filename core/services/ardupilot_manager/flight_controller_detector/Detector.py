import os
from typing import List, Optional

from loguru import logger
from serial.tools.list_ports_linux import SysFS, comports
from smbus2 import SMBus

from typedefs import FlightController, Platform


class Detector:
    @staticmethod
    def _is_root() -> bool:
        """Check if the script is running as root

        Returns:
            bool: True if running as root
        """
        return os.geteuid() == 0

    @staticmethod
    def detect_navigator() -> Optional[FlightController]:
        """Returns Navigator board if connected.
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
            except Exception:
                return False

        logger.debug("Trying to detect Navigator board.")
        if is_navigator_r5_connected():
            logger.debug("Navigator R5 detected.")
            return FlightController(name="Navigator", manufacturer="Blue Robotics", platform=Platform.Navigator)
        logger.debug("No Navigator board detected.")
        return None

    @staticmethod
    def detect_serial_platform(port: SysFS) -> Optional[Platform]:
        if port.product in ["Pixhawk1", "PX4 FMU v2.x"]:
            return Platform.Pixhawk1
        if port.product in ["Pixhawk4", "PX4 FMU v5.x"]:
            return Platform.Pixhawk4
        if port.manufacturer in ["ArduPilot", "3D Robotics"] and (port.product and not "BL" in port.product):
            return Platform.GenericSerial
        return None

    @staticmethod
    def detect_serial_flight_controllers() -> List[FlightController]:
        """Check if a Pixhawk1 or a Pixhawk4 is connected.

        Returns:
            List[FlightController]: List with connected serial flight controller.
        """
        return [
            FlightController(
                name=port.product or port.name,
                manufacturer=port.manufacturer,
                platform=Detector.detect_serial_platform(port),
                path=port.device,
            )
            for port in comports()
            if Detector.detect_serial_platform(port) is not None
        ]

    @staticmethod
    def detect_sitl() -> FlightController:
        return FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)

    @classmethod
    def detect(cls, include_sitl: bool = True) -> List[FlightController]:
        """Return a list of available flight controllers

        Returns:
            List[FlightController]: List of available flight controllers
        """
        available: List[FlightController] = []
        if not cls._is_root():
            return available

        navigator = cls.detect_navigator()
        if navigator:
            available.append(navigator)

        available.extend(cls().detect_serial_flight_controllers())

        if include_sitl:
            available.append(Detector.detect_sitl())

        return available
