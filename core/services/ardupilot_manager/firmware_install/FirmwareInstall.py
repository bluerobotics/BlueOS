import json
import os
import pathlib
import shutil
import stat

from exceptions import (
    FirmwareInstallFail,
    InvalidFirmwareFile,
    UndefinedPlatform,
    UnsupportedPlatform,
)
from firmware_download.FirmwareDownload import (
    FirmwareDownload,
    FirmwareFormat,
    Platform,
)
from firmware_upload.FirmwareUpload import FirmwareUpload


def get_board_id(platform: Platform) -> int:
    ardupilot_board_ids = {
        Platform.Pixhawk1: 9,
    }
    return ardupilot_board_ids.get(platform, -1)


class FirmwareInstaller:
    """Abstracts the install procedures for different supported boards.

    For proper usage one needs to set the platform before using other methods.

    Args:
        firmware_folder (pathlib.Path): Path for firmware folder.
    """

    def __init__(self, firmware_folder: pathlib.Path) -> None:
        self._firmware_folder: pathlib.Path = firmware_folder

    @staticmethod
    def firmware_name(platform: Platform) -> str:
        return f"ardupilot_{platform.value.lower()}"

    def firmware_path(self, platform: Platform) -> pathlib.Path:
        return pathlib.Path.joinpath(self._firmware_folder, self.firmware_name(platform))

    def is_firmware_installed(self, platform: Platform) -> bool:
        if platform == Platform.Undefined:
            raise UndefinedPlatform("Platform is undefined. Cannot verify if firmware is installed.")

        if platform == Platform.Pixhawk1:
            # Assumes for now that a Pixhawk always has a firmware installed, which is true most of the time
            # TODO: Validate if properly. The uploader tool seems capable of doing this.
            return True

        firmware_format = FirmwareDownload._supported_firmware_formats[platform]
        if firmware_format == FirmwareFormat.ELF:
            return pathlib.Path.is_file(self.firmware_path(platform))

        raise UnsupportedPlatform("Install check is not implemented for this platform.")

    @staticmethod
    def validate_firmware(firmware_path: pathlib.Path, platform: Platform) -> None:
        if platform == Platform.Undefined:
            raise UndefinedPlatform("Platform is undefined. Cannot validate firmware.")

        if platform == Platform.Pixhawk1:
            # For Pixhawk/Serial boards only .apj files are supported
            try:
                with open(firmware_path, "r") as firmware_file:
                    firmware_data = firmware_file.read()
                firmware_json = json.loads(firmware_data)
                board_id = int(firmware_json.get("board_id", -1))
                if board_id == -1:
                    raise InvalidFirmwareFile("Could not find board_id specification in the firmware file.")
                if board_id != get_board_id(platform):
                    raise InvalidFirmwareFile(f"Expected board_id {get_board_id(platform)}, found {board_id}.")
                return
            except Exception as error:
                raise InvalidFirmwareFile(f"Could not load firmware file for validation: {error}") from error

        firmware_format = FirmwareDownload._supported_firmware_formats[platform]
        if firmware_format == FirmwareFormat.ELF:
            # TODO: Include firmware validation through Ardupilot's ardupilot_fw_decoder.py
            return

        raise UnsupportedPlatform("Firmware validation is not implemented for this platform.")

    @staticmethod
    def add_run_permission(firmware_path: pathlib.Path) -> None:
        # Make the binary executable
        ## S_IX: Execution permission for
        ##    OTH: Others
        ##    USR: User
        ##    GRP: Group
        ## For more information: https://www.gnu.org/software/libc/manual/html_node/Permission-Bits.html
        os.chmod(firmware_path, firmware_path.stat().st_mode | stat.S_IXOTH | stat.S_IXUSR | stat.S_IXGRP)

    def install_firmware(self, new_firmware_path: pathlib.Path, platform: Platform) -> None:
        if platform == Platform.Undefined:
            raise UndefinedPlatform("Platform is undefined. Cannot install firmware.")

        if not new_firmware_path.is_file():
            raise InvalidFirmwareFile("Given path is not a valid file.")

        firmware_format = FirmwareDownload._supported_firmware_formats[platform]
        if firmware_format == FirmwareFormat.ELF:
            self.add_run_permission(new_firmware_path)

        self.validate_firmware(new_firmware_path, platform)

        try:
            if platform == Platform.Pixhawk1:
                firmware_uploader = FirmwareUpload()
                firmware_uploader.upload(new_firmware_path)
                return
            if firmware_format == FirmwareFormat.ELF:
                # Using copy() instead of move() since the last can't handle cross-device properly (e.g. docker binds)
                shutil.copy(new_firmware_path, self.firmware_path(platform))
                os.remove(new_firmware_path)
                return
        except Exception as error:
            raise FirmwareInstallFail(f"Error installing firmware: {error}") from error

        raise UnsupportedPlatform("Firmware install is not implemented for this platform.")
