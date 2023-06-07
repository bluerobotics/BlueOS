import pathlib
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from loguru import logger

from exceptions import (
    FirmwareInstallFail,
    NoDefaultFirmwareAvailable,
    NoVersionAvailable,
    UnsupportedPlatform,
)
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareInstall import FirmwareInstaller
from typedefs import (
    Firmware,
    FirmwareFormat,
    FlightController,
    Parameters,
    Platform,
    PlatformType,
    Vehicle,
)


class FirmwareManager:
    def __init__(
        self, firmware_folder: pathlib.Path, defaults_folder: pathlib.Path, user_defaults_folder: pathlib.Path
    ) -> None:
        self.firmware_folder = firmware_folder
        self.defaults_folder = defaults_folder
        self.user_defaults_folder = user_defaults_folder
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

    def default_user_firmware_path(self, platform: Platform) -> pathlib.Path:
        """Get path of user-defined default firmware for given platform."""
        return pathlib.Path.joinpath(self.user_defaults_folder, self.firmware_name(platform) + "_default")

    def default_user_params_path(self, platform: Platform) -> pathlib.Path:
        """Get path of user-defined default firmware for given platform."""
        return pathlib.Path.joinpath(self.user_defaults_folder, self.firmware_name(platform) + "params.params")

    def default_firmware_path(self, platform: Platform) -> pathlib.Path:
        """Get path of default firmware for given platform."""
        if self.default_user_firmware_path(platform).is_file():
            return self.default_user_firmware_path(platform)
        return pathlib.Path.joinpath(self.defaults_folder, self.firmware_name(platform))

    def is_default_firmware_available(self, platform: Platform) -> bool:
        return pathlib.Path.is_file(self.default_firmware_path(platform)) or pathlib.Path.is_file(
            self.default_user_firmware_path(platform)
        )

    def is_firmware_installed(self, board: FlightController) -> bool:
        """Check if firmware for given platform is installed."""
        if board.type == PlatformType.Serial:
            # Assumes for now that a serial board always has a firmware installed, which is true most of the time
            # TODO: Validate if properly. The uploader tool seems capable of doing this.
            return True

        firmware_format = FirmwareDownloader._supported_firmware_formats[board.platform.type]
        if firmware_format == FirmwareFormat.ELF:
            return pathlib.Path.is_file(self.firmware_path(board.platform))

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

    def install_firmware_from_file(
        self, new_firmware_path: pathlib.Path, board: FlightController, default_parameters: Optional[Parameters] = None
    ) -> None:
        if default_parameters is not None:
            if board.platform.type == PlatformType.Serial:
                self.embed_params_into_apj(new_firmware_path, default_parameters)
            else:
                self.save_params_to_default_linux_path(board.platform, default_parameters)
        try:
            if board.type == PlatformType.Serial:
                self.firmware_installer.install_firmware(new_firmware_path, board)
            else:
                self.firmware_installer.install_firmware(new_firmware_path, board, self.firmware_path(board.platform))
            logger.info(f"Succefully installed firmware for {board.name}.")
        except Exception as error:
            raise FirmwareInstallFail("Could not install firmware.") from error

    def embed_params_into_apj(self, firmware_path: Path, default_parameters: Parameters) -> None:
        # create a temporary file
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp:
            # write each parameter to the file
            for param, value in default_parameters.params.items():
                temp.write(f"{param}={value}\n")
            # make sure all data is written to the file
            temp.flush()
            # construct the command as a list of strings
            command = ["apj_tool.py", str(firmware_path), "--set-file", temp.name]
            # use subprocess.run to execute the command
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            # check for errors
            if result.returncode != 0:
                logger.error(f"Error setting parameters: {result.stderr}")

        # clean up the temporary file
        Path(temp.name).unlink()

    def save_params_to_default_linux_path(self, platform: Platform, default_parameters: Optional[Parameters]) -> None:
        # write the params to the default params file as csv format
        if default_parameters:
            with open(self.default_user_params_path(platform), "w", encoding="utf-8") as f:
                for key in default_parameters.params.keys():
                    f.write(f"{key},{default_parameters.params[key]}\n")
        else:
            # if no params are provided, delete the file if it exists
            if self.default_user_params_path(platform).is_file():
                self.default_user_params_path(platform).unlink()

    def install_firmware_from_url(
        self,
        url: str,
        board: FlightController,
        makeDefault: bool = False,
        default_parameters: Optional[Parameters] = None,
    ) -> None:
        temporary_file = self.firmware_download._download(url.strip())
        if default_parameters is not None:
            if board.platform.type == PlatformType.Serial:
                self.embed_params_into_apj(temporary_file, default_parameters)
            else:
                self.save_params_to_default_linux_path(board.platform, default_parameters)
        if makeDefault:
            shutil.copy(temporary_file, self.default_user_firmware_path(board.platform))
        self.install_firmware_from_file(temporary_file, board, default_parameters)

    def install_firmware_from_params(self, vehicle: Vehicle, board: FlightController, version: str = "") -> None:
        url = self.firmware_download.get_download_url(vehicle, board.platform, version)
        self.install_firmware_from_url(url, board)

    def restore_default_firmware(self, board: FlightController) -> None:
        if not self.is_default_firmware_available(board.platform):
            raise NoDefaultFirmwareAvailable(f"Default firmware not available for '{board.name}'.")

        self.install_firmware_from_file(self.default_firmware_path(board.platform), board)

    @staticmethod
    def validate_firmware(firmware_path: pathlib.Path, platform: Platform) -> None:
        FirmwareInstaller.validate_firmware(firmware_path, platform)
