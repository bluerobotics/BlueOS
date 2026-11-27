import asyncio
import struct
import time
from typing import Optional

import serial
from loguru import logger

# MAVLink protocol constants
MAVLINK_V2_MAGIC = 0xFD
MAVLINK_V1_MAGIC = 0xFE
MAVLINK_V2_HEADER_LEN = 10
MAVLINK_V1_HEADER_LEN = 6
MAVLINK_CRC_LEN = 2
MAVLINK_SIGNATURE_LEN = 13
MAVLINK_IFLAG_SIGNED = 0x01
AUTOPILOT_VERSION_MSG_ID = 148
AUTOPILOT_VERSION_CRC_EXTRA = 178
AUTOPILOT_VERSION_PAYLOAD_LEN = 78
BOARD_ID_OFFSET = 28  # Offset in AUTOPILOT_VERSION payload where board_id is located
BOARD_ID_SHIFT = 16  # Shift to extract board type from full board_id (upper 16 bits)

# Hardcoded MAVLink COMMAND_LONG message to request AUTOPILOT_VERSION
# This is MAVLink 2.0: system_id=255, component_id=0, requesting message ID 148
REQUEST_AUTOPILOT_VERSION_MSG = bytes.fromhex(
    "fd1e000000ff004c0000000014430000000000000000000000000000000000000000000000000002ec38"
)


def x25_crc(data: bytes, crc: int = 0xFFFF) -> int:
    """CRC-16/MCRF4XX, the checksum used by MAVLink."""
    for byte in data:
        tmp = byte ^ (crc & 0xFF)
        tmp = (tmp ^ (tmp << 4)) & 0xFF
        crc = ((crc >> 8) ^ (tmp << 8) ^ (tmp << 3) ^ (tmp >> 4)) & 0xFFFF
    return crc


def _parse_frame_at(data: bytes, start: int) -> Optional[int]:
    """Return board_version of a valid AUTOPILOT_VERSION frame starting at `start`, None otherwise."""
    if data[start] == MAVLINK_V2_MAGIC:
        header_len = MAVLINK_V2_HEADER_LEN
        if start + header_len > len(data):
            return None
        msg_id = int.from_bytes(data[start + 7 : start + 10], "little")
        signature_len = MAVLINK_SIGNATURE_LEN if data[start + 2] & MAVLINK_IFLAG_SIGNED else 0
    else:
        header_len = MAVLINK_V1_HEADER_LEN
        if start + header_len > len(data):
            return None
        msg_id = data[start + 5]
        signature_len = 0

    payload_len = data[start + 1]
    if msg_id != AUTOPILOT_VERSION_MSG_ID or payload_len > AUTOPILOT_VERSION_PAYLOAD_LEN:
        return None

    payload_end = start + header_len + payload_len
    if payload_end + MAVLINK_CRC_LEN + signature_len > len(data):
        return None

    crc = x25_crc(data[start + 1 : payload_end] + bytes([AUTOPILOT_VERSION_CRC_EXTRA]))
    if crc != int.from_bytes(data[payload_end : payload_end + MAVLINK_CRC_LEN], "little"):
        return None

    # MAVLink 2 removes trailing zeros from the payload
    payload = data[start + header_len : payload_end].ljust(AUTOPILOT_VERSION_PAYLOAD_LEN, b"\x00")
    return int(struct.unpack_from("<I", payload, BOARD_ID_OFFSET)[0])


def parse_autopilot_version_board_id(data: bytes) -> Optional[int]:
    """
    Find a valid MAVLink 1 or 2 AUTOPILOT_VERSION (ID 148) frame in `data` and return its board_version field
    (uint32 at offset 28 of the payload). Frames with invalid length or CRC are ignored.

    Args:
        data: Raw bytes from serial port

    Returns:
        board_version as integer, or None if no valid frame was found
    """
    for start, byte in enumerate(data):
        if byte not in (MAVLINK_V2_MAGIC, MAVLINK_V1_MAGIC):
            continue
        board_version = _parse_frame_at(data, start)
        if board_version is not None:
            return board_version
    return None


def _get_board_id_sync(port_path: str, baudrate: int = 115200) -> Optional[int]:
    """
    Synchronous implementation of board_id retrieval.
    Internal function - use get_board_id() instead.

    Returns the board type ID (upper 16 bits of the full board_id).
    """
    try:
        # Set a short timeout for individual reads
        with serial.Serial(port_path, baudrate, timeout=0.2, exclusive=True, write_timeout=0) as ser:
            # Send the hardcoded request message
            ser.write(REQUEST_AUTOPILOT_VERSION_MSG)
            # Read response with a maximum wait time of 200ms
            response_data = b""
            start_time = time.time()
            max_wait_time = 0.2  # 200ms
            while time.time() - start_time < max_wait_time:
                # Only read what's available in the buffer to avoid blocking
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    response_data += chunk
                    # Try parsing what we have so far
                    board_id = parse_autopilot_version_board_id(response_data)
                    if board_id is not None:
                        # Return board type ID (upper 16 bits)
                        return board_id >> BOARD_ID_SHIFT
                else:
                    time.sleep(0.01)
            # Final attempt to parse all collected data
            board_id = parse_autopilot_version_board_id(response_data)
            if board_id is not None:
                # Return board type ID (upper 16 bits)
                return board_id >> BOARD_ID_SHIFT
            logger.debug(f"no board id found on {port_path}")
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.flush()
            return None

    except serial.SerialException as e:
        logger.debug(f"Serial port error on {port_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting board version on {port_path}: {e}")
        return None


async def get_board_id(port_path: str, baudrate: int = 115200) -> Optional[int]:
    """
    Connect to serial port, request AUTOPILOT_VERSION, and extract board_id.

    This function does NOT require pymavlink - it uses hardcoded request bytes
    and manually parses the response.

    This is an async function that runs the blocking serial I/O in a thread pool
    to avoid blocking the event loop.

    Args:
        port_path: Serial port path (e.g., '/dev/ttyUSB0', '/dev/ttyACM0')
        baudrate: Baud rate for serial communication (default: 115200)

    Returns:
        Board type ID (upper 16 bits of board_id) as integer, or None if failed
    """
    start = time.time()
    board_id = await asyncio.to_thread(_get_board_id_sync, port_path, baudrate)
    end = time.time()
    logger.debug(f"get_board_id to port {port_path} took {end - start} seconds")
    return board_id
