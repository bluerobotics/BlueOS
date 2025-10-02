from enum import Enum
from dataclasses import dataclass
import time
import serial


class PX4BootLoaderCommands(int, Enum):
    # Protocol Bytes
    PROTO_INSYNC = 0x12  # 'in sync' byte sent before status
    PROTO_BAD_SILICON_REV = 0x14  # Device is using silicon not suitable
    PROTO_EOC = 0x20  # End of command

    # Reply bytes
    PROTO_OK = 0x10  # 'ok' response
    PROTO_FAILED = 0x11  # 'fail' response
    PROTO_INVALID = 0x13  # 'invalid' response for bad commands

    # Command bytes
    PROTO_GET_SYNC = 0x21  # NOP for re-establishing sync
    PROTO_GET_DEVICE = 0x22  # get device ID bytes
    PROTO_CHIP_ERASE = 0x23  # erase program area and reset program address
    PROTO_LOAD_ADDRESS = 0x24  # set next programming address
    PROTO_PROG_MULTI = 0x27  # write bytes at program address and increment
    PROTO_GET_CRC = 0x29  # compute & return a CRC
    PROTO_BOOT = 0x30  # boot the application

    # Command bytes - Rev 2 boootloader only
    PROTO_CHIP_VERIFY = 0x24  # begin verify mode
    PROTO_READ_MULTI = 0x28  # read bytes at programm address and increment

    INFO_BL_REV = 1  # bootloader protocol revision
    BL_REV_MIN = 2  # Minimum supported bootlader protocol
    BL_REV_MAX = 5  # Maximum supported bootloader protocol
    INFO_BOARD_ID = 2  # board type
    INFO_BOARD_REV = 3  # board revision
    INFO_FLASH_SIZE = 4  # max firmware size in bytes

    PROG_MULTI_MAX = (64,)  # write size for PROTO_PROG_MULTI, must be multiple of 4
    READ_MULTI_MAX = 0x28  # read size for PROTO_READ_MULTI, must be multiple of 4. Sik Radio max size is 0x28


@dataclass
class PX4BootLoaderBoardInfo:
    board_id: int
    boot_loader_version: int
    flash_size: int


class PX4BootLoader:
    # Specific boards that need special handling when in certain versions of boot loader
    _board_id_px4_fmu_v2 = 9
    _board_id_px4_fmu_v3 = 255
    _board_flash_size_small = 1032192
    _boot_loader_version_v2_correct_flash = 5

    def __init__(self, port: serial.Serial):
        self.port = port

    def get_board_info(self) -> PX4BootLoaderBoardInfo:
        # Try getting in sync
        self._sync()

        # Get bootloader version
        bootloader_version = self._proto_get_device(PX4BootLoaderCommands.INFO_BL_REV)

        if (
            bootloader_version < PX4BootLoaderCommands.BL_REV_MIN
            or bootloader_version > PX4BootLoaderCommands.BL_REV_MAX
        ):
            raise ValueError("Unsupported bootloader version")

        # Get board ID
        board_id = self._proto_get_device(PX4BootLoaderCommands.INFO_BOARD_ID)

        # Get flash size
        flash_size = self._proto_get_device(PX4BootLoaderCommands.INFO_FLASH_SIZE)

        # From QGC source code
        # Older V2 boards have large flash space but silicon error which prevents it from being used. Bootloader v5 and above
        # will correctly account/report for this. Older bootloaders will not. Newer V2 board which support larger flash space are
        # reported as V3 board id.
        if (
            board_id == self._board_id_px4_fmu_v2
            and bootloader_version >= self._boot_loader_version_v2_correct_flash
            and flash_size > self._board_flash_size_small
        ):
            board_id = self._board_id_px4_fmu_v3

        return PX4BootLoaderBoardInfo(board_id, bootloader_version, flash_size)

    def _safe_read(self, expected_bytes: int, timeout: int) -> bytearray:
        started_reading_at = time.time()
        while self.port.in_waiting < expected_bytes:
            if time.time() - started_reading_at > timeout:
                raise serial.SerialTimeoutException("Timeout while waiting bootloader response")
            time.sleep(0.1)

        return bytearray(self.port.read(expected_bytes))

    def _read_command_response(self, timeout: int) -> bytearray:
        # By default PX4 responses are 2 bytes long
        res = self._safe_read(2, timeout)

        if res[0] != PX4BootLoaderCommands.PROTO_INSYNC:
            raise serial.SerialException("Unable to sync with bootloader")
        if res[0] == PX4BootLoaderCommands.PROTO_INSYNC and res[1] == PX4BootLoaderCommands.PROTO_BAD_SILICON_REV:
            raise serial.SerialException("Device is using silicon not suitable")

        if res[1] == PX4BootLoaderCommands.PROTO_FAILED:
            raise serial.SerialException("Failed to execute command")
        if res[1] == PX4BootLoaderCommands.PROTO_INVALID:
            raise serial.SerialException("Invalid command")

        return res

    def _safe_serial_write(self, data: bytearray) -> None:
        bytes_written = self.port.write(data)
        if bytes_written != len(data):
            raise serial.SerialException("Invalid number of bytes written to serial port")

    def _send_serial_command(self, command: PX4BootLoaderCommands, timeout: int = 1) -> None:
        buffer = bytearray([command, PX4BootLoaderCommands.PROTO_EOC])

        self._safe_serial_write(buffer)
        self.port.flush()

        self._read_command_response(timeout)

    def _sync(self) -> None:
        # Clear the buffer prior to syncing
        self.port.read_all()

        # Getting in sync some times requires multiple attempts
        for _ in range(10):
            try:
                self._send_serial_command(PX4BootLoaderCommands.PROTO_GET_SYNC)
                return
            except Exception:
                time.sleep(0.1)

        raise RuntimeError("Failed to sync with bootloader")

    def _proto_get_device(self, command: PX4BootLoaderCommands) -> int:
        buffer = bytearray([PX4BootLoaderCommands.PROTO_GET_DEVICE, command, PX4BootLoaderCommands.PROTO_EOC])

        self._safe_serial_write(buffer)
        val = self._safe_read(4, 1)
        self._read_command_response(1)

        return int.from_bytes(val, byteorder="little")
