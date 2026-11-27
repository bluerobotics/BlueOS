import asyncio
import json
import pathlib
import platform
from typing import Union

import pytest
from ardupilot_fw_decoder import BoardSubType, BoardType
from exceptions import InvalidFirmwareFile
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import (
    FirmwareInstaller,
    get_correspondent_decoder_platform,
)
from typedefs import FlightController, Platform, PlatformType, Vehicle

Pixhawk1 = FlightController(
    name="Pixhawk1",
    platform=Platform(name="Pixhawk1", platform_type=PlatformType.Serial),
    ardupilot_board_id=9,
)
Pixhawk4 = FlightController(
    name="Pixhawk4",
    manufacturer="Holybro",
    platform=Platform(name="Pixhawk4", platform_type=PlatformType.Serial),
    ardupilot_board_id=50,
)
SITL = FlightController(name="SITL", manufacturer="ArduPilot Team", platform=Platform.SITL())
GenericSerial = FlightController(
    name="GenericSerial",
    platform=Platform(name="GenericSerial", platform_type=PlatformType.Serial),
)
Navigator = FlightController(
    name="Navigator",
    manufacturer="Blue Robotics",
    platform=Platform(name="Navigator", platform_type=PlatformType.Linux),
)


def test_firmware_validation() -> None:
    async def firmware_validation_wrapper() -> None:
        downloader = FirmwareDownloader()
        installer = FirmwareInstaller()

        # Pixhawk1 and Pixhawk4 APJ firmwares should always work
        temporary_file = await downloader.download(Vehicle.Sub, Pixhawk1)
        installer.validate_firmware(temporary_file, Pixhawk1)

        temporary_file = await downloader.download(Vehicle.Sub, Pixhawk4)
        installer.validate_firmware(temporary_file, Pixhawk4)

        # New SITL firmwares should always work, except for MacOS
        # there are no SITL builds for MacOS
        if platform.system() != "Darwin":
            temporary_file = await downloader.download(Vehicle.Sub, SITL, version="DEV")
            installer.validate_firmware(temporary_file, SITL)

        # Raise when validating Navigator firmwares (as test platform is x86)
        temporary_file = await downloader.download(Vehicle.Sub, Navigator)
        with pytest.raises(InvalidFirmwareFile):
            installer.validate_firmware(temporary_file, Navigator)

        # Install SITL firmware
        if platform.system() != "Darwin":
            # there are no SITL builds for MacOS
            temporary_file = await downloader.download(Vehicle.Sub, SITL, version="DEV")
            await installer.install_firmware(temporary_file, SITL, pathlib.Path(f"{temporary_file}_dest"))

    asyncio.run(firmware_validation_wrapper())


def test_apj_validation_for_generic_serial(tmp_path: pathlib.Path) -> None:
    firmware_path = tmp_path / "custom.apj"
    firmware_path.write_text(json.dumps({"board_id": 1013}), encoding="utf-8")
    FirmwareInstaller.validate_firmware(firmware_path, GenericSerial)


def test_apj_validation_requires_board_id(tmp_path: pathlib.Path) -> None:
    firmware_path = tmp_path / "custom.apj"
    firmware_path.write_text(json.dumps({"image": ""}), encoding="utf-8")
    for board in (Pixhawk1, GenericSerial):
        with pytest.raises(InvalidFirmwareFile, match="Could not find board_id"):
            FirmwareInstaller.validate_firmware(firmware_path, board)


@pytest.mark.parametrize(
    "board_platform, decoder_platform",
    [
        (Platform(name="Navigator", platform_type=PlatformType.Linux), BoardSubType.LINUX_NAVIGATOR),
        (Platform(name="navigator64", platform_type=PlatformType.Linux), BoardSubType.LINUX_NAVIGATOR),
        (Platform(name="Argonot", platform_type=PlatformType.Linux), BoardSubType.LINUX_NAVIGATOR),
        (Platform(name="Navio2", platform_type=PlatformType.Linux), BoardType.EMPTY),
        (Platform.SITL(), BoardType.SITL),
        (Platform(name="Pixhawk1", platform_type=PlatformType.Serial), BoardType.EMPTY),
    ],
)
def test_decoder_platform_mapping(board_platform: Platform, decoder_platform: Union[BoardType, BoardSubType]) -> None:
    assert get_correspondent_decoder_platform(board_platform) == decoder_platform


def test_apj_validation_reports_board_id_mismatch(tmp_path: pathlib.Path) -> None:
    firmware_path = tmp_path / "custom.apj"
    firmware_path.write_text(json.dumps({"board_id": 1013}), encoding="utf-8")
    with pytest.raises(InvalidFirmwareFile, match="Expected board_id 9, found 1013"):
        FirmwareInstaller.validate_firmware(firmware_path, Pixhawk1)
