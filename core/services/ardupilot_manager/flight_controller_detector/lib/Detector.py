import os
from enum import Enum
from typing import List

from smbus2 import SMBus


class FlightControllerType(Enum):
    Serial = 1
    Navigator = 2


class Detector:
    @staticmethod
    def _is_root() -> bool:
        """Check if the script is running as root

        Returns:
            bool: True if running as root
        """
        return os.geteuid() == 0

    @staticmethod
    def detect_navigator() -> bool:
        """Check if navigator is connected using the sensors on the I²C BUS

        Returns:
            bool: True if a serial navigator is connected
        """
        try:
            bus = SMBus(1)
            PCA9685_address = 0x40
            ADS115_address = 0x48

            bus.read_byte_data(PCA9685_address, 0)
            bus.read_byte_data(ADS115_address, 0)
            return True
        except Exception as error:
            print(f"Navigator not detected on I2C bus: {error}")
            return False

    @staticmethod
    def detect_serial_flight_controller() -> bool:
        """Check if a pixhawk or any serial valid flight controller is connected

        Returns:
            bool: True if a serial flight controller is connected
        """
        return os.path.exists("/dev/autopilot")

    @staticmethod
    def detect() -> List[FlightControllerType]:
        """Return a list of available flight controllers

        Returns:
            List[FlightControllerType]: List of available flight controllers
        """
        available = []
        if Detector._is_root() and Detector.detect_navigator():
            available.append(FlightControllerType.Navigator)

        if Detector.detect_serial_flight_controller():
            available.append(FlightControllerType.Serial)

        return available
