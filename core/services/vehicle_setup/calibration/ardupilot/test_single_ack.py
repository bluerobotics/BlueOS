import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from calibration.ardupilot.preflight import preflight_command
from calibration.ardupilot.single_ack import (
    PREFLIGHT_KINDS,
    SingleAckState,
    cancel,
    on_message,
    start_large_vehicle_compass,
    start_preflight,
)
from vehicle_setup_types import CalibrationKind, CalibrationStatus

FAILURES = [
    "MAV_RESULT_CANCELLED",
    "MAV_RESULT_DENIED",
    "MAV_RESULT_FAILED",
    "MAV_RESULT_TEMPORARILY_REJECTED",
    "MAV_RESULT_UNSUPPORTED",
]


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


@pytest.mark.parametrize(
    "kind, param, value",
    [
        (CalibrationKind.GYROSCOPE, 1, 1),
        (CalibrationKind.BAROMETER, 3, 1),
        (CalibrationKind.ACCELEROMETER, 5, 1),
        (CalibrationKind.BOARD_LEVEL, 5, 2),
        (CalibrationKind.SIMPLE_ACCELEROMETER, 5, 4),
    ],
)
def test_preflight_params_match_the_frontend(kind: CalibrationKind, param: int, value: float) -> None:
    params = preflight_command(kind).params
    assert len(params) == 7
    assert {index + 1: param_value for index, param_value in enumerate(params) if param_value} == {param: value}


def test_the_full_accelerometer_is_not_single_ack() -> None:
    with pytest.raises(ValueError):
        start_preflight(CalibrationKind.ACCELEROMETER)


@pytest.mark.parametrize("kind", [CalibrationKind.GYROSCOPE, CalibrationKind.BOARD_LEVEL])
@pytest.mark.parametrize("result", [*FAILURES, "MAV_RESULT_COMMAND_INT_ONLY"])
def test_non_accepted_ack_fails(kind: CalibrationKind, result: str) -> None:
    state, _ = start_preflight(kind)
    state = replay(state, [ack(result)])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason is not None and result in state.reason
    assert not state.reboot_required


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


def test_cancel_is_a_no_op() -> None:
    # ArduPilot can't cancel these; the calibration still ends with its ack
    state, _ = start_preflight(CalibrationKind.BAROMETER)
    assert cancel(state) == (state, [])
    assert replay(state, [ack("MAV_RESULT_ACCEPTED")]).status == CalibrationStatus.DONE


def test_large_vehicle_compass_keeps_coordinate_decimals() -> None:
    _, commands = start_large_vehicle_compass(0b011, -27.5935, -48.5585)
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
    assert cancel(state) == (state, [])
    state = replay(state, [ack("MAV_RESULT_ACCEPTED", "MAV_CMD_FIXED_MAG_CAL_YAW")])
    assert state.status == CalibrationStatus.DONE
    assert state.reboot_required


def test_large_vehicle_compass_refused() -> None:
    state, _ = start_large_vehicle_compass(0b001, 0.0, 0.0)
    state = replay(state, [ack("MAV_RESULT_FAILED", "MAV_CMD_FIXED_MAG_CAL_YAW")])
    assert state.status == CalibrationStatus.FAILED
    assert not state.reboot_required
