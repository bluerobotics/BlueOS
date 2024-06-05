from typing import List

from commonwealth.utils.commands import load_file

from flight_controller_detector.linux.linux_boards import LinuxFlightController
from typedefs import Platform, Serial


class Navigator(LinuxFlightController):
    name = "Navigator"
    manufacturer = "Blue Robotics"
    platform = Platform.Navigator

    def is_pi5(self) -> bool:
        with open("/proc/cpuinfo", "r", encoding="utf-8") as f:
            return "Raspberry Pi 5" in f.read()

    def detect(self) -> bool:
        return False

    def get_serials(self) -> List[Serial]:
        raise NotImplementedError


class NavigatorPi5(Navigator):
    devices = {
        "ADS1115": (0x48, 1),
        "AK09915": (0x0C, 1),
        "BME280": (0x76, 1),
        "PCA9685": (0x40, 3),
    }

    def get_serials(self) -> List[Serial]:
        return [
            Serial(port="C", endpoint="/dev/ttyAMA0"),
            Serial(port="B", endpoint="/dev/ttyAMA2"),
            Serial(port="E", endpoint="/dev/ttyAMA3"),
            Serial(port="F", endpoint="/dev/ttyAMA4"),
        ]

    def detect(self) -> bool:
        if not self.is_pi5():
            return False
        return all(self.check_for_i2c_device(bus, address) for address, bus in self.devices.values())


class NavigatorPi4(Navigator):
    devices = {
        "ADS1115": (0x48, 1),
        "AK09915": (0x0C, 1),
        "BME280": (0x76, 1),
        "PCA9685": (0x40, 4),
    }

    def get_serials(self) -> List[Serial]:
        release = "Bullseye"
        os_release = load_file("/etc/os-release")
        if "bookworm" in os_release:
            release = "Bookworm"

        match release:
            case "Bullseye":
                return [
                    Serial(port="C", endpoint="/dev/ttyS0"),
                    Serial(port="B", endpoint="/dev/ttyAMA1"),
                    Serial(port="E", endpoint="/dev/ttyAMA2"),
                    Serial(port="F", endpoint="/dev/ttyAMA3"),
                ]
            case "Bookworm":
                return [
                    Serial(port="C", endpoint="/dev/ttyS0"),
                    Serial(port="B", endpoint="/dev/ttyAMA3"),
                    Serial(port="E", endpoint="/dev/ttyAMA4"),
                    Serial(port="F", endpoint="/dev/ttyAMA5"),
                ]
        raise RuntimeError("Unknown release, unable to map ports")

    def detect(self) -> bool:
        if self.is_pi5():
            return False
        return all(self.check_for_i2c_device(bus, address) for address, bus in self.devices.values())
