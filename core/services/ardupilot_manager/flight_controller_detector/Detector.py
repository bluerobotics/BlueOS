import os
from enum import IntEnum
from typing import List, Tuple

from loguru import logger
from smbus2 import SMBus


class FlightControllerType(IntEnum):
    Serial = 1
    NavigatorR3 = 2
    NavigatorR4 = 3


class Detector:
    @staticmethod
    def _is_root() -> bool:
        """Check if the script is running as root

        Returns:
            bool: True if running as root
        """
        return os.geteuid() == 0

    @staticmethod
    def detect_navigator_r3() -> Tuple[bool, str]:
        """Check if navigator R3 is connected using the sensors on the I²C BUS

        Returns:
            (bool, str): True if a navigator is connected, false otherwise.
                String is always empty
        """
        try:
            bus = SMBus(1)
            ADS1115_address = 0x48
            bus.read_byte_data(ADS1115_address, 0)

            bus = SMBus(4)
            PCA9685_address = 0x40
            bus.read_byte_data(PCA9685_address, 0)

            return (True, "")
        except Exception as error:
            logger.info("Navigator R3 not detected on I2C bus.")
            logger.debug(error)
            return (False, "")

    @staticmethod
    def detect_navigator_r4() -> Tuple[bool, str]:
        """Check if navigator R4 is connected using the sensors on the I²C BUS

        Returns:
            (bool, str): True if a navigator is connected, false otherwise.
                String is always empty
        """
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

            return (True, "")
        except Exception as error:
            logger.info("Navigator R4 not detected on I2C bus.")
            logger.debug(error)
            return (False, "")

    @staticmethod
    def detect_serial_flight_controller() -> Tuple[bool, str]:
        """Check if a pixhawk or any serial valid flight controller is connected

        Returns:
            (bool, str): True if a serial flight controller is connected, false otherwise.
                String will point to the serial device.
        """
        serial_path = "/dev/autopilot"
        result = (True, serial_path) if os.path.exists(serial_path) else (False, "")
        return result

    @staticmethod
    def detect() -> List[Tuple[FlightControllerType, str]]:
        """Return a list of available flight controllers

        Returns:
            (FlightControllerType, str): List of available flight controllers
        """
        available = []
        if Detector._is_root():
            # We should detect R4 first since it shares some sensors as R3
            result, path = Detector.detect_navigator_r4()
            if result:
                available.append((FlightControllerType.NavigatorR4, path))
            else:
                result, path = Detector.detect_navigator_r3()
                if result:
                    available.append((FlightControllerType.NavigatorR3, path))

        result, path = Detector.detect_serial_flight_controller()
        if result:
            available.append((FlightControllerType.Serial, path))

        return available
