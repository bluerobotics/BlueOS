from typing import Optional
import asyncio
import struct
import time
import serial
from loguru import logger

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
    """
    i = 0
    while i < len(data):
        # Look for MAVLink 2.0 magic byte
        if data[i] == 0xFD:
            if i + 10 > len(data):
                break

            msg_id = struct.unpack("<I", data[i + 7 : i + 10] + b"\x00")[0]  # 24-bit little endian

            # Check if this is AUTOPILOT_VERSION (148)
            if msg_id == 148:
                header_len = 10
                payload_start = i + header_len

                if payload_start + 32 <= len(data):  # board_id is at offset 28, uint32 = 4 bytes
                    # Extract board_id (uint32 at offset 28)
                    board_id_bytes = data[payload_start + 28 : payload_start + 32]
                    board_id = struct.unpack("<I", board_id_bytes)[0]
                    return int(board_id)

            i += 1
        # Also check for MAVLink 1.0 magic byte (0xFE) just in case
        elif data[i] == 0xFE:
            if i + 6 > len(data):
                break

            msg_id = data[i + 5]

            # AUTOPILOT_VERSION is usually MAVLink 2.0, but handle just in case
            if msg_id == 148:
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
    """
    try:
        # Set a short timeout for individual reads
        with serial.Serial(port_path, baudrate, timeout=0.2, exclusive=True) as ser:
            # Clear any existing data
            ser.reset_input_buffer()

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
                        return board_id >> 16
                else:
                    # If nothing is waiting, do a small blocking read to wait for data
                    # This will timeout after 200ms (set in Serial constructor)
                    chunk = ser.read(1)
                    if not chunk:
                        break
                    response_data += chunk

            # Final attempt to parse all collected data
            board_id = parse_autopilot_version_board_id(response_data)
            if board_id is not None:
                return int(board_id) >> 16
            return None

    except serial.SerialException as e:
        print(f"Serial port error on {port_path}: {e}")
        return None
    except Exception as e:
        print(f"Error getting board version: {e}")
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
        board_id as integer, or None if failed
    """
    start = time.time()
    board_id = await asyncio.to_thread(_get_board_id_sync, port_path, baudrate)
    end = time.time()
    logger.info(f"get_board_id took {end - start} seconds")
    return board_id
