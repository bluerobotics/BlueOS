import platform
from typing import Any, List

from commonwealth.utils.commands import load_file
from commonwealth.utils.general import CpuType, get_cpu_type
from elftools.elf.elffile import ELFFile
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from typedefs import Platform, Serial


class Navigator(LinuxFlightController):
    manufacturer = "Blue Robotics"

    def __init__(self, **data: Any) -> None:
        name = "Navigator"
        plat = Platform.Navigator
        if platform.machine() == "aarch64":
            # edge case for 64-bit kernel on 32-bit userland...
            # let's check the arch for /usr/bin/ls
            with open("/usr/bin/ls", "rb") as f:
                elf_file = ELFFile(f)
                firm_arch = elf_file.get_machine_arch()
                # from https://github.com/eliben/pyelftools/blob/main/elftools/elf/elffile.py#L513
                if firm_arch == "AArch64":
                    name = "Navigator64"
                    plat = Platform.Navigator64
        super().__init__(**data, name=name, platform=plat)

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
            Serial(port=1, endpoint="/dev/ttyAMA0"),
            Serial(port=3, endpoint="/dev/ttyAMA2"),
            Serial(port=4, endpoint="/dev/ttyAMA3"),
            Serial(port=5, endpoint="/dev/ttyAMA4"),
        ]

    def detect(self) -> bool:
        if not get_cpu_type() == CpuType.PI5:
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
        if "bookworm" in os_release.lower():
            release = "Bookworm"

        match release:
            case "Bullseye":
                return [
                    Serial(port="1", endpoint="/dev/ttyS0"),
                    Serial(port="3", endpoint="/dev/ttyAMA1"),
                    Serial(port="4", endpoint="/dev/ttyAMA2"),
                    Serial(port="5", endpoint="/dev/ttyAMA3"),
                ]
            case "Bookworm":
                return [
                    Serial(port="1", endpoint="/dev/ttyS0"),
                    Serial(port="3", endpoint="/dev/ttyAMA3"),
                    Serial(port="4", endpoint="/dev/ttyAMA4"),
                    Serial(port="5", endpoint="/dev/ttyAMA5"),
                ]
        raise RuntimeError("Unknown release, unable to map ports")

    def detect(self) -> bool:
        if not get_cpu_type() == CpuType.PI4:
            return False
        return all(self.check_for_i2c_device(bus, address) for address, bus in self.devices.values())
