import pathlib
from typing import List

from loguru import logger

from exceptions import (
    FirmwareInstallFail,
    NoDefaultFirmwareAvailable,
    NoVersionAvailable,
    UnsupportedPlatform,
)
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import Firmware, FirmwareFormat, Platform, Vehicle


class FirmwareManager:
    def __init__(self, firmware_folder: pathlib.Path, defaults_folder: pathlib.Path) -> None:
        self.firmware_folder = firmware_folder
        self.defaults_folder = defaults_folder
        self.firmware_download = FirmwareDownloader()
        self.firmware_installer = FirmwareInstaller()

    @staticmethod
    def firmware_name(platform: Platform) -> str:
        """Get consistent firmware name for given platform."""
        return f"ardupilot_{platform.value.lower()}"

    def firmware_path(self, platform: Platform) -> pathlib.Path:
        """Get firmware's path for given platform. This is the path where we expect to find
        a valid Ardupilot binary for Linux boards."""
        return pathlib.Path.joinpath(self.firmware_folder, self.firmware_name(platform))

    def default_firmware_path(self, platform: Platform) -> pathlib.Path:
        """Get path of default firmware for given platform."""
        return pathlib.Path.joinpath(self.defaults_folder, self.firmware_name(platform))

    def is_default_firmware_available(self, platform: Platform) -> bool:
        return pathlib.Path.is_file(self.default_firmware_path(platform))

    def is_firmware_installed(self, platform: Platform) -> bool:
        """Check if firmware for given platform is installed."""
        if platform == Platform.Pixhawk1:
            # Assumes for now that a Pixhawk always has a firmware installed, which is true most of the time
            # TODO: Validate if properly. The uploader tool seems capable of doing this.
            return True

        firmware_format = FirmwareDownloader._supported_firmware_formats[platform]
        if firmware_format == FirmwareFormat.ELF:
            return pathlib.Path.is_file(self.firmware_path(platform))

        raise UnsupportedPlatform("Install check is not implemented for this platform.")

    def get_available_firmwares(self, vehicle: Vehicle, platform: Platform) -> List[Firmware]:
        firmwares = []
        versions = self.firmware_download.get_available_versions(vehicle, platform)
        if not versions:
            raise NoVersionAvailable(f"Failed to find any version for vehicle {vehicle}.")
        for version in versions:
            try:
                url = self.firmware_download.get_download_url(vehicle, platform, version)
                firmware = Firmware(name=version, url=url)
                firmwares.append(firmware)
            except Exception as error:
                logger.debug(f"Error fetching URL for version {version} on vehicle {vehicle}: {error}")
        if not firmwares:
            raise NoVersionAvailable(f"Failed do get any valid URL for vehicle {vehicle}.")
        return firmwares

    def install_firmware_from_file(self, new_firmware_path: pathlib.Path, platform: Platform) -> None:
        try:
            if platform == Platform.Pixhawk1:
                self.firmware_installer.install_firmware(new_firmware_path, platform)
            else:
                self.firmware_installer.install_firmware(new_firmware_path, platform, self.firmware_path(platform))
            logger.info(f"Succefully installed firmware for {platform}.")
        except Exception as error:
            error_message = f"Could not install firmware: {error}"
            logger.exception(error_message)
            raise FirmwareInstallFail(error_message) from error

    def install_firmware_from_url(self, url: str, platform: Platform) -> None:
        temporary_file = self.firmware_download._download(url.strip())
        self.install_firmware_from_file(temporary_file, platform)

    def install_firmware_from_params(self, vehicle: Vehicle, platform: Platform, version: str = "") -> None:
        url = self.firmware_download.get_download_url(vehicle, platform, version)
        self.install_firmware_from_url(url, platform)

    def restore_default_firmware(self, platform: Platform) -> None:
        if not self.is_default_firmware_available(platform):
            raise NoDefaultFirmwareAvailable(f"Default firmware not available for platform '{platform}'.")

        self.install_firmware_from_file(self.default_firmware_path(platform), platform)

    @staticmethod
    def validate_firmware(firmware_path: pathlib.Path, platform: Platform) -> None:
        FirmwareInstaller.validate_firmware(firmware_path, platform)
