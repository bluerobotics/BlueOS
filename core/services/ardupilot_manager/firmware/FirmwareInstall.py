import json
import os
import pathlib
import platform as system_platform
import shutil
import stat
from typing import Optional, Union

from ardupilot_fw_decoder import BoardSubType, BoardType, Decoder
from elftools.elf.elffile import ELFFile
from exceptions import FirmwareInstallFail, InvalidFirmwareFile, UnsupportedPlatform
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareUpload import FirmwareUploader
from loguru import logger
from typedefs import FirmwareFormat, FlightController, Platform, PlatformType


def get_board_id(platform: Platform) -> int:
    ardupilot_board_ids = {
        Platform.Pixhawk1: 9,
        Platform.Pixhawk4: 50,
        Platform.Pixhawk6X: 53,
        Platform.Pixhawk6C: 56,
        Platform.CubeOrange: 140,
    }
    return ardupilot_board_ids.get(platform, -1)


def is_valid_elf_type(elf_arch: str) -> bool:
    arch_mapping = {"i386": "x86", "x86_64": "x64", "armv7l": "ARM", "aarch64": "AArch64"}
    system_arch = system_platform.machine()
    system_arch = arch_mapping.get(system_arch, system_arch)

    if system_arch == elf_arch:
        return True
    if system_arch == "AArch64" and elf_arch == "ARM":
        return True
    return False


def get_correspondent_decoder_platform(current_platform: Platform) -> Union[BoardType, BoardSubType]:
    correspondent_decoder_platform = {
        Platform.SITL: BoardType.SITL,
        Platform.Navigator: BoardSubType.LINUX_NAVIGATOR,
        Platform.Argonot: BoardSubType.LINUX_NAVIGATOR,
        Platform.Navigator64: BoardSubType.LINUX_NAVIGATOR,
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
        except (OSError, json.JSONDecodeError) as error:
            raise InvalidFirmwareFile(f"Could not load firmware file for validation: {firmware_path}") from error

        if platform == Platform.GenericSerial:
            logger.warning("Skipping board_id validation for GenericSerial platform.")
            return

        expected_board_id = get_board_id(platform)
        if expected_board_id == -1:
            raise UnsupportedPlatform("Firmware validation is not implemented for this board yet.")
        if firm_board_id == -1:
            raise InvalidFirmwareFile("Could not find board_id specification in the firmware file.")
        if firm_board_id != expected_board_id:
            raise InvalidFirmwareFile(f"Expected board_id {expected_board_id}, found {firm_board_id}.")
        return

    @staticmethod
    def _validate_elf(firmware_path: pathlib.Path, platform: Platform) -> None:
        # Check if firmware's architecture matches system's architecture
        with open(firmware_path, "rb") as file:
            try:
                elf_file = ELFFile(file)
                firm_arch = elf_file.get_machine_arch()
            except Exception as error:
                raise InvalidFirmwareFile("Given file is not a valid ELF.") from error
        if not is_valid_elf_type(firm_arch):
            raise InvalidFirmwareFile(
                f"Firmware's architecture ({firm_arch}) does not match system's ({system_platform.machine()})."
            )

        # Check if firmware's platform matches system platform
        try:
            firm_decoder = Decoder()
            firm_decoder.process(firmware_path)
            firm_board = BoardType(firm_decoder.fwversion.board_type)
            firm_sub_board = BoardSubType(firm_decoder.fwversion.board_subtype)
            current_decoder_platform = get_correspondent_decoder_platform(platform)
            logger.debug(
                f"firm_board: {firm_board}, firm_sub_board: {firm_sub_board}, current_decoder_platform: {current_decoder_platform}"
            )
            if current_decoder_platform not in [firm_board, firm_sub_board]:
                raise InvalidFirmwareFile(
                    (
                        f"Firmware's platform ({current_decoder_platform}) does not match system's ({platform}),"
                        f"for board ({firm_board}) or sub board ({firm_sub_board})."
                    )
                )
        except Exception as error:
            raise InvalidFirmwareFile("Given firmware is not a supported version.") from error

    @staticmethod
    def validate_firmware(firmware_path: pathlib.Path, platform: Platform) -> None:
        """Check if given firmware is valid for given platform."""
        firmware_format = FirmwareDownloader._supported_firmware_formats[platform.type]

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

    async def install_firmware(
        self,
        new_firmware_path: pathlib.Path,
        board: FlightController,
        firmware_dest_path: Optional[pathlib.Path] = None,
    ) -> None:
        """Install given firmware."""
        if not new_firmware_path.is_file():
            raise InvalidFirmwareFile("Given path is not a valid file.")

        firmware_format = FirmwareDownloader._supported_firmware_formats[board.platform.type]
        if firmware_format == FirmwareFormat.ELF:
            self.add_run_permission(new_firmware_path)

        self.validate_firmware(new_firmware_path, board.platform)

        if board.type == PlatformType.Serial:
            firmware_uploader = FirmwareUploader()
            if not board.path:
                raise ValueError("Board path not available.")
            firmware_uploader.set_autopilot_port(pathlib.Path(board.path))
            await firmware_uploader.upload(new_firmware_path)
            return
        if firmware_format == FirmwareFormat.ELF:
            # Using copy() instead of move() since the last can't handle cross-device properly (e.g. docker binds)
            if not firmware_dest_path:
                raise FirmwareInstallFail("Firmware file destination not provided.")
            shutil.copy(new_firmware_path, firmware_dest_path)
            return

        raise UnsupportedPlatform("Firmware install is not implemented for this platform.")
