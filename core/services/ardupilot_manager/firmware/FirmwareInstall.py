import json
import os
import pathlib
import platform as system_platform
import shutil
import stat
from typing import Optional, Union

from ardupilot_fw_decoder import BoardSubType, BoardType, Decoder
from elftools.elf.elffile import ELFFile

from exceptions import (
    FirmwareInstallFail,
    InvalidFirmwareFile,
    UndefinedPlatform,
    UnsupportedPlatform,
)
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareUpload import FirmwareUploader
from typedefs import FirmwareFormat, Platform


def get_board_id(platform: Platform) -> int:
    ardupilot_board_ids = {
        Platform.Pixhawk1: 9,
    }
    return ardupilot_board_ids.get(platform, -1)


def get_correspondent_elf_arch(platform_arch: str) -> str:
    correspondent_elf_archs = {
        "x86_64": "x64",
        "armv7l": "ARM",
    }
    return correspondent_elf_archs.get(platform_arch, "")


def get_correspondent_decoder_platform(current_platform: Platform) -> Union[BoardType, BoardSubType]:
    correspondent_decoder_platform = {
        Platform.SITL: BoardType.SITL,
        Platform.NavigatorR3: BoardSubType.LINUX_NAVIGATOR,
        Platform.NavigatorR5: BoardSubType.LINUX_NAVIGATOR,
    }
    return correspondent_decoder_platform.get(current_platform, BoardType.EMPTY)


class FirmwareInstaller:
    """Abstracts the install procedures for different supported boards.

    For proper usage one needs to set the platform before using other methods.

    Args:
        firmware_folder (pathlib.Path): Path for firmware folder.
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _validate_apj(firmware_path: pathlib.Path, platform: Platform) -> None:
        try:
            with open(firmware_path, "r", encoding="utf-8") as firmware_file:
                firmware_data = firmware_file.read()
                firm_board_id = int(json.loads(firmware_data).get("board_id", -1))
            expected_board_id = get_board_id(platform)
            if expected_board_id == -1:
                raise UnsupportedPlatform("Firmware validation is not implemented for this board yet.")
            if firm_board_id == -1:
                raise InvalidFirmwareFile("Could not find board_id specification in the firmware file.")
            if firm_board_id != expected_board_id:
                raise InvalidFirmwareFile(f"Expected board_id {expected_board_id}, found {firm_board_id}.")
            return
        except Exception as error:
            raise InvalidFirmwareFile(f"Could not load firmware file for validation: {error}") from error

    @staticmethod
    def _validate_elf(firmware_path: pathlib.Path, platform: Platform) -> None:
        # Check if firmware's architecture matches system's architecture
        with open(firmware_path, "rb") as file:
            try:
                elf_file = ELFFile(file)
                firm_arch = elf_file.get_machine_arch()
            except Exception as error:
                raise InvalidFirmwareFile(f"Given file is not a valid ELF: {error}") from error
        running_arch = system_platform.machine()
        if firm_arch != get_correspondent_elf_arch(running_arch):
            raise InvalidFirmwareFile(
                f"Firmware's architecture ({firm_arch}) does not match system's ({running_arch})."
            )

        # Check if firmware's platform matches system platform
        try:
            firm_decoder = Decoder()
            firm_decoder.process(firmware_path)
            firm_board = firm_decoder.fwversion.board_type
            firm_sub_board = firm_decoder.fwversion.board_subtype
            current_decoder_platform = get_correspondent_decoder_platform(platform)
            if not current_decoder_platform in [firm_board, firm_sub_board]:
                InvalidFirmwareFile(
                    f"Firmware's platform ({current_decoder_platform}) does not match system's ({platform})."
                )
        except Exception as error:
            raise InvalidFirmwareFile("Given firmware is not a supported version.") from error

    @staticmethod
    def validate_firmware(firmware_path: pathlib.Path, platform: Platform) -> None:
        """Check if given firmware is valid for given platform."""
        if platform == Platform.Undefined:
            raise UndefinedPlatform("Platform is undefined. Cannot validate firmware.")

        firmware_format = FirmwareDownloader._supported_firmware_formats[platform]

        if firmware_format == FirmwareFormat.APJ:
            FirmwareInstaller._validate_apj(firmware_path, platform)
            return

        if firmware_format == FirmwareFormat.ELF:
            FirmwareInstaller._validate_elf(firmware_path, platform)
            return

        raise UnsupportedPlatform("Firmware validation is not implemented for this platform.")

    @staticmethod
    def add_run_permission(firmware_path: pathlib.Path) -> None:
        """Add running permission for firmware file."""
        # Make the binary executable
        ## S_IX: Execution permission for
        ##    OTH: Others
        ##    USR: User
        ##    GRP: Group
        ## For more information: https://www.gnu.org/software/libc/manual/html_node/Permission-Bits.html
        os.chmod(firmware_path, firmware_path.stat().st_mode | stat.S_IXOTH | stat.S_IXUSR | stat.S_IXGRP)

    def install_firmware(
        self, new_firmware_path: pathlib.Path, platform: Platform, firmware_dest_path: Optional[pathlib.Path] = None
    ) -> None:
        """Install given firmware."""
        if platform == Platform.Undefined:
            raise UndefinedPlatform("Platform is undefined. Cannot install firmware.")

        if not new_firmware_path.is_file():
            raise InvalidFirmwareFile("Given path is not a valid file.")

        firmware_format = FirmwareDownloader._supported_firmware_formats[platform]
        if firmware_format == FirmwareFormat.ELF:
            self.add_run_permission(new_firmware_path)

        self.validate_firmware(new_firmware_path, platform)

        try:
            if platform == Platform.Pixhawk1:
                firmware_uploader = FirmwareUploader()
                firmware_uploader.upload(new_firmware_path)
                return
            if firmware_format == FirmwareFormat.ELF:
                # Using copy() instead of move() since the last can't handle cross-device properly (e.g. docker binds)
                if not firmware_dest_path:
                    raise FirmwareInstallFail("Firmware file destination not provided.")
                shutil.copy(new_firmware_path, firmware_dest_path)
                return
        except Exception as error:
            raise FirmwareInstallFail(f"Error installing firmware: {error}") from error

        raise UnsupportedPlatform("Firmware install is not implemented for this platform.")
