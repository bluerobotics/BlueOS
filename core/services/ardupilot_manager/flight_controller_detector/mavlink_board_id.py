import asyncio
import struct
import time
from typing import Optional

import serial
from loguru import logger

# MAVLink protocol constants
MAVLINK_V2_MAGIC = 0xFD
MAVLINK_V1_MAGIC = 0xFE
AUTOPILOT_VERSION_MSG_ID = 148
BOARD_ID_OFFSET = 28  # Offset in AUTOPILOT_VERSION payload where board_id is located
BOARD_ID_SHIFT = 16  # Shift to extract board type from full board_id (upper 16 bits)

# Hardcoded MAVLink COMMAND_LONG message to request AUTOPILOT_VERSION
# This is MAVLink 2.0: system_id=255, component_id=0, requesting message ID 148
REQUEST_AUTOPILOT_VERSION_MSG = bytes.fromhex(
    "fd1e000000ff004c0000000014430000000000000000000000000000000000000000000000000002ec38"
)


def parse_autopilot_version_board_id(data: bytes) -> Optional[int]:
    """
    Manually parse MAVLink AUTOPILOT_VERSION message to extract board_id field.

    The AUTOPILOT_VERSION message (ID 148) has the following structure:
    - Header: 1 byte (magic byte 0xFD for MAVLink 2.0)
    - Payload length: 1 byte
    - Incompatibility flags: 1 byte
    - Compatibility flags: 1 byte
    - Sequence: 1 byte
    - System ID: 1 byte
    - Component ID: 1 byte
    - Message ID: 3 bytes (little endian)
    - Payload: variable
    - Checksum: 2 bytes

    In the AUTOPILOT_VERSION payload, board_id is at offset 28 (uint32)

    Args:
        data: Raw bytes from serial port

    Returns:
        board_id as integer, or None if parsing fails

    Raises:
        ValueError: If MAVLink 1.0 protocol is detected
    """
    i = 0
    while i < len(data):
        # Look for MAVLink 2.0 magic byte
        if data[i] == MAVLINK_V2_MAGIC:
            if i + 10 > len(data):
                break

            msg_id = struct.unpack("<I", data[i + 7 : i + 10] + b"\x00")[0]  # 24-bit little endian

            # Check if this is AUTOPILOT_VERSION
            if msg_id == AUTOPILOT_VERSION_MSG_ID:
                header_len = 10
                payload_start = i + header_len

                if payload_start + BOARD_ID_OFFSET + 4 <= len(data):  # board_id is uint32 (4 bytes)
                    # Extract board_id (uint32 at BOARD_ID_OFFSET)
                    board_id_bytes = data[payload_start + BOARD_ID_OFFSET : payload_start + BOARD_ID_OFFSET + 4]
                    board_id = struct.unpack("<I", board_id_bytes)[0]
                    return int(board_id)

            i += 1
        # Raise error if MAVLink 1.0 is detected
        elif data[i] == MAVLINK_V1_MAGIC:
            if i + 6 > len(data):
                break
            msg_id = data[i + 5]
            # AUTOPILOT_VERSION is usually MAVLink 2.0, but handle just in case
            if msg_id == AUTOPILOT_VERSION_MSG_ID:
                header_len = 6
                payload_start = i + header_len
                if payload_start + 32 <= len(data):
                    board_id_bytes = data[payload_start + 28 : payload_start + 32]
                    board_id = struct.unpack("<I", board_id_bytes)[0]
                    return int(board_id)
            i += 1
        else:
            i += 1

    return None


def _get_board_id_sync(port_path: str, baudrate: int = 115200) -> Optional[int]:
    """
    Synchronous implementation of board_id retrieval.
    Internal function - use get_board_id() instead.

    Returns the board type ID (upper 16 bits of the full board_id).

    Raises:
        ValueError: If MAVLink 1.0 protocol is detected
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
            logger.info(f"no board id found on {port_path}")
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.flush()
            return None

    except ValueError as e:
        # Specifically handle MAVLink 1.0 detection
        logger.error(f"Protocol error on {port_path}: {e}")
        raise  # Re-raise to inform caller about unsupported protocol
    except serial.SerialException as e:
        logger.error(f"Serial port error on {port_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error getting board version: {e}")
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

    Raises:
        ValueError: If MAVLink 1.0 protocol is detected
    """
    start = time.time()
    board_id = await asyncio.to_thread(_get_board_id_sync, port_path, baudrate)
    end = time.time()
    logger.info(f"get_board_id to port {port_path} took {end - start} seconds")
    return board_id
