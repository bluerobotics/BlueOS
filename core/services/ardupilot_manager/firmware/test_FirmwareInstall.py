import pathlib
import platform

import pytest

from exceptions import InvalidFirmwareFile
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import FlightController, Platform, Vehicle

Pixhawk1 = FlightController(name="Pixhawk1", manufacturer="3DR", platform=Platform.Pixhawk1)
Pixhawk4 = FlightController(name="Pixhawk4", manufacturer="Holybro", platform=Platform.Pixhawk4)
SITL = FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)
Navigator = FlightController(name="Navigator", manufacturer="Blue Robotics", platform=Platform.Navigator)


def test_firmware_validation() -> None:
    downloader = FirmwareDownloader()
    installer = FirmwareInstaller()

    # Pixhawk1 and Pixhawk4 APJ firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Pixhawk1)
    installer.validate_firmware(temporary_file, Pixhawk1)

    temporary_file = downloader.download(Vehicle.Sub, Pixhawk4)
    installer.validate_firmware(temporary_file, Pixhawk4)

    # New SITL firmwares should always work, except for MacOS
    # there are no SITL builds for MacOS
    if platform.system() != "Darwin":
        temporary_file = downloader.download(Vehicle.Sub, SITL, version="DEV")
        installer.validate_firmware(temporary_file, SITL)

    # Raise when validating Navigator firmwares (as test platform is x86)
    temporary_file = downloader.download(Vehicle.Sub, Navigator)
    with pytest.raises(InvalidFirmwareFile):
        installer.validate_firmware(temporary_file, Navigator)

    # Install SITL firmware
    if platform.system() != "Darwin":
        # there are no SITL builds for MacOS
        temporary_file = downloader.download(Vehicle.Sub, SITL, version="DEV")
        installer.install_firmware(temporary_file, SITL, pathlib.Path(f"{temporary_file}_dest"))
