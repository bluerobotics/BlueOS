import time
from dataclasses import dataclass
from enum import IntEnum

import serial
from loguru import logger


class PX4BootLoaderProtocol(IntEnum):
    INSYNC = 0x12  # 'in sync' byte sent before status
    EOC = 0x20  # End of command

    # Reply bytes
    OK = 0x10  # 'ok' response
    FAILED = 0x11  # 'fail' response
    INVALID = 0x13  # 'invalid' response for bad commands
    BAD_SILICON_REV = 0x14  # Device is using silicon not suitable


class PX4BootLoaderCommand(IntEnum):
    GET_SYNC = 0x21  # NOP for re-establishing sync
    GET_DEVICE = 0x22  # get device ID bytes
    BOOT = 0x30  # boot the application


class PX4BootLoaderDeviceInfo(IntEnum):
    """Parameters of the GET_DEVICE command"""

    BL_REV = 1  # bootloader protocol revision
    BOARD_ID = 2  # board type
    BOARD_REV = 3  # board revision
    FLASH_SIZE = 4  # max firmware size in bytes


BL_REV_MIN = 2  # Minimum supported bootloader protocol
BL_REV_MAX = 5  # Maximum supported bootloader protocol

# Only used to probe ports, a device that is not a bootloader must not hold the detection for long
SYNC_ATTEMPTS = 3
COMMAND_TIMEOUT_SECONDS = 0.5


@dataclass
class PX4BootLoaderBoardInfo:
    board_id: int
    boot_loader_version: int
    flash_size: int


class PX4BootLoader:
    def __init__(self, port: serial.Serial):
        self.port = port

    def get_board_info(self) -> PX4BootLoaderBoardInfo:
        # Try getting in sync
        self._sync()

        # Get bootloader version
        bootloader_version = self._proto_get_device(PX4BootLoaderDeviceInfo.BL_REV)

        if bootloader_version < BL_REV_MIN or bootloader_version > BL_REV_MAX:
            raise ValueError(f"Unsupported bootloader version {bootloader_version}")

        board_id = self._proto_get_device(PX4BootLoaderDeviceInfo.BOARD_ID)
        flash_size = self._proto_get_device(PX4BootLoaderDeviceInfo.FLASH_SIZE)

        return PX4BootLoaderBoardInfo(board_id, bootloader_version, flash_size)

    def boot(self) -> None:
        """Ask the bootloader to boot the application. It stops its autoboot timeout after any valid command."""
        try:
            self.port.write(bytearray([PX4BootLoaderCommand.BOOT, PX4BootLoaderProtocol.EOC]))
            self.port.flush()
        except serial.SerialException as error:
            logger.debug(f"Failed to ask bootloader to boot: {error}")

    def _safe_read(self, expected_bytes: int, timeout: float) -> bytearray:
        started_reading_at = time.time()
        while self.port.in_waiting < expected_bytes:
            if time.time() - started_reading_at > timeout:
                raise serial.SerialTimeoutException("Timeout while waiting bootloader response")
            time.sleep(0.1)

        return bytearray(self.port.read(expected_bytes))

    def _read_command_response(self, timeout: float) -> bytearray:
        # By default PX4 responses are 2 bytes long
        res = self._safe_read(2, timeout)

        if res[0] != PX4BootLoaderProtocol.INSYNC:
            raise serial.SerialException("Unable to sync with bootloader")
        if res[1] == PX4BootLoaderProtocol.BAD_SILICON_REV:
            raise serial.SerialException("Device is using silicon not suitable")
        if res[1] == PX4BootLoaderProtocol.FAILED:
            raise serial.SerialException("Failed to execute command")
        if res[1] == PX4BootLoaderProtocol.INVALID:
            raise serial.SerialException("Invalid command")

        return res

    def _safe_serial_write(self, data: bytearray) -> None:
        bytes_written = self.port.write(data)
        if bytes_written != len(data):
            raise serial.SerialException("Invalid number of bytes written to serial port")

    def _send_serial_command(self, command: PX4BootLoaderCommand, timeout: float = COMMAND_TIMEOUT_SECONDS) -> None:
        buffer = bytearray([command, PX4BootLoaderProtocol.EOC])

        self._safe_serial_write(buffer)
        self.port.flush()

        self._read_command_response(timeout)

    def _sync(self) -> None:
        # Clear the buffer prior to syncing
        self.port.read_all()

        # Getting in sync some times requires multiple attempts
        for _ in range(SYNC_ATTEMPTS):
            try:
                self._send_serial_command(PX4BootLoaderCommand.GET_SYNC)
                return
            except serial.SerialException:
                time.sleep(0.1)

        raise RuntimeError("Failed to sync with bootloader")

    def _proto_get_device(self, param: PX4BootLoaderDeviceInfo) -> int:
        buffer = bytearray([PX4BootLoaderCommand.GET_DEVICE, param, PX4BootLoaderProtocol.EOC])

        self._safe_serial_write(buffer)
        val = self._safe_read(4, COMMAND_TIMEOUT_SECONDS)
        self._read_command_response(COMMAND_TIMEOUT_SECONDS)

        return int.from_bytes(val, byteorder="little")
