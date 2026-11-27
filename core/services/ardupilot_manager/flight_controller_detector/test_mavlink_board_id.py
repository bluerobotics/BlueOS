from typing import Any, List

import pytest
import serial
from flight_controller_detector import mavlink_board_id
from flight_controller_detector.mavlink_board_id import (
    AUTOPILOT_VERSION_CRC_EXTRA,
    AUTOPILOT_VERSION_MSG_ID,
    REQUEST_AUTOPILOT_VERSION_MSG,
    parse_autopilot_version_board_id,
    x25_crc,
)

COMMAND_LONG_CRC_EXTRA = 152
CUBE_ORANGE_BOARD_VERSION = (140 << 16) | 0x1234


def autopilot_version_payload(board_version: int) -> bytes:
    payload = bytearray(78)
    payload[0:8] = (0xFFFF).to_bytes(8, "little")  # capabilities
    payload[28:32] = board_version.to_bytes(4, "little")
    payload[32:34] = (0x1209).to_bytes(2, "little")  # vendor_id
    return bytes(payload)


def v2_frame(payload: bytes, msg_id: int = AUTOPILOT_VERSION_MSG_ID, incompat_flags: int = 0) -> bytes:
    header = bytes([len(payload), incompat_flags, 0, 7, 1, 1]) + msg_id.to_bytes(3, "little")
    crc = x25_crc(header + payload + bytes([AUTOPILOT_VERSION_CRC_EXTRA]))
    signature = bytes(range(13)) if incompat_flags & 0x01 else b""
    return b"\xfd" + header + payload + crc.to_bytes(2, "little") + signature


def v1_frame(payload: bytes) -> bytes:
    header = bytes([len(payload), 7, 1, 1, AUTOPILOT_VERSION_MSG_ID])
    crc = x25_crc(header + payload + bytes([AUTOPILOT_VERSION_CRC_EXTRA]))
    return b"\xfe" + header + payload + crc.to_bytes(2, "little")


def test_request_message_is_a_valid_command_long() -> None:
    message = REQUEST_AUTOPILOT_VERSION_MSG
    assert len(message) == 10 + message[1] + 2
    assert int.from_bytes(message[7:10], "little") == 76  # COMMAND_LONG
    crc = x25_crc(message[1:-2] + bytes([COMMAND_LONG_CRC_EXTRA]))
    assert crc == int.from_bytes(message[-2:], "little")


def test_valid_v2_frame() -> None:
    frame = v2_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION))
    assert parse_autopilot_version_board_id(b"garbage" + frame + b"\x00\x01") == CUBE_ORANGE_BOARD_VERSION


def test_truncated_v2_payload_is_zero_padded() -> None:
    # MAVLink 2 strips trailing zeros, the last byte of board_version (9 << 16) is zero too
    payload = bytearray(78)
    payload[0] = 1
    payload[28:32] = (9 << 16).to_bytes(4, "little")
    truncated = bytes(payload).rstrip(b"\x00")
    assert len(truncated) == 31
    assert parse_autopilot_version_board_id(v2_frame(truncated)) == 9 << 16


def test_bad_crc_is_rejected() -> None:
    frame = bytearray(v2_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION)))
    frame[-1] ^= 0xFF
    assert parse_autopilot_version_board_id(bytes(frame)) is None


def test_incomplete_frame_is_rejected() -> None:
    frame = v2_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION))
    assert parse_autopilot_version_board_id(frame[:-1]) is None


def test_garbage_and_ubx_data_is_rejected() -> None:
    # UBX NAV-PVT like data, containing both MAVLink magic bytes and the AUTOPILOT_VERSION id
    ubx = b"\xb5\x62\x01\x07\x5c\x00" + bytes([0xFD, 0x4E, 0, 0, 0, 1, 1, 148, 0, 0]) + bytes(range(256)) * 2
    assert parse_autopilot_version_board_id(ubx) is None
    assert parse_autopilot_version_board_id(b"\xfd" * 300 + b"\xfe" * 300) is None
    assert parse_autopilot_version_board_id(b"") is None


def test_other_messages_are_ignored() -> None:
    heartbeat = v2_frame(bytes(9), msg_id=0)
    assert parse_autopilot_version_board_id(heartbeat) is None
    frame = v2_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION))
    assert parse_autopilot_version_board_id(heartbeat + frame) == CUBE_ORANGE_BOARD_VERSION


def test_signed_v2_frame() -> None:
    frame = v2_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION), incompat_flags=0x01)
    assert parse_autopilot_version_board_id(frame) == CUBE_ORANGE_BOARD_VERSION
    assert parse_autopilot_version_board_id(frame[:-1]) is None


def test_v1_frame() -> None:
    frame = v1_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION)[:60])
    assert parse_autopilot_version_board_id(frame) == CUBE_ORANGE_BOARD_VERSION


class FakeSerial:
    def __init__(self, response: bytes) -> None:
        self.response = bytearray(response)
        self.written: List[bytes] = []

    def __call__(self, *_args: Any, **_kwargs: Any) -> "FakeSerial":
        return self

    def __enter__(self) -> "FakeSerial":
        return self

    def __exit__(self, *_args: Any) -> None:
        pass

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    @property
    def in_waiting(self) -> int:
        return len(self.response)

    def read(self, size: int) -> bytes:
        data = bytes(self.response[:size])
        del self.response[:size]
        return data

    def reset_input_buffer(self) -> None:
        pass

    def reset_output_buffer(self) -> None:
        pass

    def flush(self) -> None:
        pass


def test_get_board_id_returns_board_type(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeSerial(v2_frame(autopilot_version_payload(CUBE_ORANGE_BOARD_VERSION)))
    monkeypatch.setattr(serial, "Serial", fake)
    assert mavlink_board_id._get_board_id_sync("/dev/ttyACM0") == 140
    assert fake.written == [REQUEST_AUTOPILOT_VERSION_MSG]


def test_get_board_id_without_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(serial, "Serial", FakeSerial(b"\x00" * 10))
    assert mavlink_board_id._get_board_id_sync("/dev/ttyACM0") is None
