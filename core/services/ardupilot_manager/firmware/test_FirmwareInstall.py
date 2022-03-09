import pathlib

import pytest

from exceptions import InvalidFirmwareFile
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import FlightController, Platform, Vehicle


def test_firmware_validation() -> None:
    downloader = FirmwareDownloader()
    installer = FirmwareInstaller()

    # Pixhawk1 APJ firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Platform.Pixhawk1)
    installer.validate_firmware(temporary_file, Platform.Pixhawk1)

    # New SITL firmwares should always work
    temporary_file = downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
    installer.validate_firmware(temporary_file, Platform.SITL)

    # Raise when validating Navigator firmwares (as test platform is x86)
    temporary_file = downloader.download(Vehicle.Sub, Platform.Navigator)
    with pytest.raises(InvalidFirmwareFile):
        installer.validate_firmware(temporary_file, Platform.Navigator)

    # Install SITL firmware
    temporary_file = downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
    board = FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)
    installer.install_firmware(temporary_file, board, pathlib.Path(f"{temporary_file}_dest"))
