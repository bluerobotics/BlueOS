import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from calibration import ardupilot
from calibration.ardupilot.single_ack import (
    PREFLIGHT_KINDS,
    SingleAckState,
    on_message,
    start_large_vehicle_compass,
    start_preflight,
)
from vehicle_setup_types import CalibrationKind, CalibrationStatus, StartCalibration


def ack(result: str, command: str = "MAV_CMD_PREFLIGHT_CALIBRATION") -> Dict[str, Any]:
    return {"type": "COMMAND_ACK", "command": {"type": command}, "result": {"type": result}}


def replay(state: SingleAckState, messages: List[Dict[str, Any]]) -> SingleAckState:
    for message in messages:
        state, commands = on_message(state, message)
        assert not commands
    return state


@pytest.mark.parametrize("kind", PREFLIGHT_KINDS)
def test_one_command_one_ack(kind: CalibrationKind) -> None:
    state, commands = start_preflight(kind)
    assert [command.command for command in commands] == ["MAV_CMD_PREFLIGHT_CALIBRATION"]
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [ack("MAV_RESULT_ACCEPTED")])
    assert state.status == CalibrationStatus.DONE
    assert state.reason is None
    assert state.reboot_required == (kind == CalibrationKind.BOARD_LEVEL)


def test_a_refused_ack_fails_without_a_reboot() -> None:
    state, _ = start_preflight(CalibrationKind.BOARD_LEVEL)
    state = replay(state, [ack("MAV_RESULT_DENIED")])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason is not None and "MAV_RESULT_DENIED" in state.reason
    assert not state.reboot_required


def test_an_unknown_result_ends_it_as_unknown() -> None:
    state, _ = start_preflight(CalibrationKind.GYROSCOPE)
    state = replay(state, [ack("MAV_RESULT_NEW"), ack("MAV_RESULT_ACCEPTED")])
    assert (state.status, state.reboot_required) == (CalibrationStatus.UNKNOWN, False)
    assert (
        state.reason
        == "MAV_CMD_PREFLIGHT_CALIBRATION answered MAV_RESULT_NEW, which this version of BlueOS doesn't know"
    )


def test_in_progress_keeps_running() -> None:
    state, _ = start_preflight(CalibrationKind.BAROMETER)
    state = replay(state, [ack("MAV_RESULT_IN_PROGRESS"), ack("MAV_RESULT_IN_PROGRESS")])
    assert state.status == CalibrationStatus.RUNNING
    assert replay(state, [ack("MAV_RESULT_ACCEPTED")]).status == CalibrationStatus.DONE


def test_other_messages_are_ignored() -> None:
    state, _ = start_preflight(CalibrationKind.SIMPLE_ACCELEROMETER)
    state = replay(
        state,
        [
            ack("MAV_RESULT_FAILED", "MAV_CMD_REQUEST_MESSAGE"),
            ack("MAV_RESULT_ACCEPTED", "MAV_CMD_DO_START_MAG_CAL"),
            {"type": "HEARTBEAT", "mavtype": {"type": "MAV_TYPE_SUBMARINE"}},
            {"type": "COMMAND_LONG", "command": {"type": "MAV_CMD_ACCELCAL_VEHICLE_POS"}, "param1": 1.0},
        ],
    )
    assert state.status == CalibrationStatus.RUNNING
    assert replay(state, [ack("MAV_RESULT_FAILED")]).status == CalibrationStatus.FAILED


def test_finished_calibration_ignores_late_acks() -> None:
    state, _ = start_preflight(CalibrationKind.GYROSCOPE)
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), ack("MAV_RESULT_FAILED")])
    assert state.status == CalibrationStatus.DONE


def test_large_vehicle_compass_keeps_coordinate_decimals() -> None:
    request = StartCalibration(
        calibration=CalibrationKind.LARGE_VEHICLE_COMPASS, compass_mask=0b011, latitude=-27.5935, longitude=-48.5585
    )
    _, commands = ardupilot.start(request)
    assert [(command.command, command.params) for command in commands] == [
        ("MAV_CMD_FIXED_MAG_CAL_YAW", [0, 0b011, -27.5935, -48.5585])
    ]


def test_large_vehicle_compass_ends_with_its_own_ack() -> None:
    state, _ = start_large_vehicle_compass(0b001, -27.5935, -48.5585)
    report = {"type": "MAG_CAL_REPORT", "compass_id": 0, "cal_status": {"type": "MAG_CAL_SUCCESS"}, "fitness": 10.0}
    state = replay(
        state,
        [
            ack("MAV_RESULT_FAILED", "MAV_CMD_DO_START_MAG_CAL"),
            report,
            ack("MAV_RESULT_IN_PROGRESS", "MAV_CMD_FIXED_MAG_CAL_YAW"),
        ],
    )
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [ack("MAV_RESULT_ACCEPTED", "MAV_CMD_FIXED_MAG_CAL_YAW")])
    assert state.status == CalibrationStatus.DONE
    assert state.reboot_required
