import os
import platform

import pytest

from firmware.FirmwareDownload import FirmwareDownloader
from typedefs import Platform, Vehicle


def test_static() -> None:
    downloaded_file = FirmwareDownloader._download(FirmwareDownloader._manifest_remote)
    assert downloaded_file, "Failed to download file."
    assert downloaded_file.exists(), "Download file does not exist."

    smaller_valid_size_bytes = 180 * 1024
    assert downloaded_file.stat().st_size > smaller_valid_size_bytes, "Download file size is not big enough."


def test_firmware_download() -> None:
    firmware_download = FirmwareDownloader()
    assert firmware_download.download_manifest(), "Failed to download/validate manifest file."

    versions = firmware_download._find_version_item(
        vehicletype="Sub", format="apj", mav_firmware_version_type="STABLE-4.0.1", platform=Platform.Pixhawk1
    )
    assert len(versions) == 1, "Failed to find a single firmware."

    versions = firmware_download._find_version_item(
        vehicletype="Sub", mav_firmware_version_type="STABLE-4.0.1", platform=Platform.Pixhawk1
    )
    # There are two versions, one for the firmware and one with the bootloader
    assert len(versions) == 2, "Failed to find multiple versions."

    available_versions = firmware_download.get_available_versions(Vehicle.Sub, Platform.Pixhawk1)
    assert len(available_versions) == len(set(available_versions)), "Available versions are not unique."

    test_available_versions = ["STABLE-4.0.1", "STABLE-4.0.0", "OFFICIAL", "DEV", "BETA"]
    assert len(set(available_versions)) >= len(
        set(test_available_versions)
    ), "Available versions are missing know versions."

    assert firmware_download.download(
        Vehicle.Sub, Platform.Pixhawk1, "STABLE-4.0.1"
    ), "Failed to download a valid firmware file."

    assert firmware_download.download(Vehicle.Sub, Platform.Pixhawk1), "Failed to download latest valid firmware file."

    assert firmware_download.download(Vehicle.Sub, Platform.Pixhawk4), "Failed to download latest valid firmware file."

    assert firmware_download.download(Vehicle.Sub, Platform.SITL), "Failed to download SITL."

    # skipt these tests for MacOS
    if platform.system() == "Darwin":
        pytest.skip("Skipping test for MacOS")
    # It'll fail if running in an arch different of ARM
    if "x86" in os.uname().machine:
        assert firmware_download.download(Vehicle.Sub, Platform.Navigator), "Failed to download navigator binary."
    else:
        with pytest.raises(Exception):
            firmware_download.download(Vehicle.Sub, Platform.Navigator)
