"""The parsing of what mavlink-server puts on zenoh, with payloads shaped like the ones mavlink-server 0.11.1 sent.

Whether the samples arrive (zenohd, mavlink-server's zenoh endpoint) needs a vehicle or SITL check.
"""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clients.mavlink import (
    AUTOPILOT_COMPONENT_ID,
    armed,
    autopilot_message,
    vehicle_heartbeat,
)
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger

ACK = {
    "type": "COMMAND_ACK",
    "command": {"type": "MAV_CMD_PREFLIGHT_CALIBRATION"},
    "result": {"type": "MAV_RESULT_ACCEPTED"},
}


def frame(system_id: Any, component_id: Any, message: Any) -> str:
    header = {"system_id": system_id, "component_id": component_id, "sequence": 0, "message_id": 0}
    return json.dumps({"header": header, "message": message})


def heartbeat(mavtype: str, base_mode: Any = "") -> Any:
    return {"type": "HEARTBEAT", "mavtype": {"type": mavtype}, "base_mode": base_mode}


def test_keeps_the_autopilots_messages() -> None:
    assert autopilot_message(frame(7, 1, ACK), 7) == ACK


@pytest.mark.parametrize(
    "text",
    [
        frame(1, 1, ACK),
        frame(7, 194, {"type": "COMMAND_LONG"}),
        frame(7, 1, {"type": "HEARTBEAT"}),
        frame(7, 1, "COMMAND_ACK"),
        json.dumps({"message": ACK}),
        json.dumps([ACK]),
        "{'header': ",
    ],
)
def test_drops_everything_else(text: str) -> None:
    assert autopilot_message(text, 7) is None


def test_a_vehicles_heartbeat_gives_its_system_id() -> None:
    beat = heartbeat("MAV_TYPE_SUBMARINE")
    assert vehicle_heartbeat(frame(7, 1, beat)) == (7, beat)


@pytest.mark.parametrize(
    "text",
    [
        frame(255, 1, heartbeat("MAV_TYPE_GCS")),
        frame(7, 1, heartbeat("MAV_TYPE_NOT_A_TYPE")),
        frame(7, 1, {"type": "HEARTBEAT"}),
        frame(7, 1, ACK),
        frame("7", 1, heartbeat("MAV_TYPE_SUBMARINE")),
        "not json",
    ],
)
def test_other_heartbeats_are_not_the_autopilots(text: str) -> None:
    assert vehicle_heartbeat(text) is None


@pytest.mark.parametrize(
    "base_mode, expected",
    [
        ("", False),
        ("MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | MAV_MODE_FLAG_STABILIZE_ENABLED", False),
        ("MAV_MODE_FLAG_SAFETY_ARMED", True),
        ("MAV_MODE_FLAG_CUSTOM_MODE_ENABLED | MAV_MODE_FLAG_SAFETY_ARMED | 0x4", True),
    ],
)
def test_armed_reads_mavlink_servers_base_mode(base_mode: str, expected: bool) -> None:
    assert armed(heartbeat("MAV_TYPE_SUBMARINE", base_mode)) is expected


def test_armed_refuses_a_base_mode_it_cant_read() -> None:
    with pytest.raises(ValueError):
        armed(heartbeat("MAV_TYPE_SUBMARINE", {"bits": 128}))


def test_our_header_is_never_the_autopilots() -> None:
    # Otherwise our own COMMAND_LONGs would pass as the autopilot's
    assert MavlinkMessenger().component_id != AUTOPILOT_COMPONENT_ID
