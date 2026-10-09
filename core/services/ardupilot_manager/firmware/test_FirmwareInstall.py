import asyncio
import json
import pathlib
import platform

import pytest
from exceptions import InvalidFirmwareFile
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import FlightController, Platform, Vehicle


def test_firmware_validation() -> None:
    async def firmware_validation_wrapper() -> None:
        downloader = FirmwareDownloader()
        installer = FirmwareInstaller()

        # Pixhawk1 and Pixhawk4 APJ firmwares should always work
        temporary_file = await downloader.download(Vehicle.Sub, Platform.Pixhawk1)
        installer.validate_firmware(temporary_file, Platform.Pixhawk1)

        temporary_file = await downloader.download(Vehicle.Sub, Platform.Pixhawk4)
        installer.validate_firmware(temporary_file, Platform.Pixhawk4)

        # New SITL firmwares should always work, except for MacOS
        # there are no SITL builds for MacOS
        if platform.system() != "Darwin":
            temporary_file = await downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
            installer.validate_firmware(temporary_file, Platform.SITL)

        # Raise when validating Navigator firmwares (as test platform is x86)
        temporary_file = await downloader.download(Vehicle.Sub, Platform.Navigator)
        with pytest.raises(InvalidFirmwareFile):
            installer.validate_firmware(temporary_file, Platform.Navigator)

        # Install SITL firmware
        if platform.system() != "Darwin":
            # there are no SITL builds for MacOS
            temporary_file = await downloader.download(Vehicle.Sub, Platform.SITL, version="DEV")
            board = FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL)
            await installer.install_firmware(temporary_file, board, pathlib.Path(f"{temporary_file}_dest"))

    asyncio.run(firmware_validation_wrapper())


def test_apj_validation_for_generic_serial(tmp_path: pathlib.Path) -> None:
    firmware_path = tmp_path / "custom.apj"
    firmware_path.write_text(json.dumps({"board_id": 1013}), encoding="utf-8")
    FirmwareInstaller.validate_firmware(firmware_path, Platform.GenericSerial)


def test_apj_validation_requires_board_id(tmp_path: pathlib.Path) -> None:
    firmware_path = tmp_path / "custom.apj"
    firmware_path.write_text(json.dumps({"image": ""}), encoding="utf-8")
    for board_platform in (Platform.Pixhawk1, Platform.GenericSerial):
        with pytest.raises(InvalidFirmwareFile, match="Could not find board_id"):
            FirmwareInstaller.validate_firmware(firmware_path, board_platform)


def test_apj_validation_reports_board_id_mismatch(tmp_path: pathlib.Path) -> None:
    firmware_path = tmp_path / "custom.apj"
    firmware_path.write_text(json.dumps({"board_id": 1013}), encoding="utf-8")
    with pytest.raises(InvalidFirmwareFile, match="Expected board_id 9, found 1013"):
        FirmwareInstaller.validate_firmware(firmware_path, Platform.Pixhawk1)
