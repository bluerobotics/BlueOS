import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration.gyro_baro import (
    GyroBaroState,
    PreflightCalibration,
    cancel,
    on_message,
    preflight_command,
    start,
)
from vehicle_setup_types import CalibrationStatus

FAILURES = [
    "MAV_RESULT_CANCELLED",
    "MAV_RESULT_DENIED",
    "MAV_RESULT_FAILED",
    "MAV_RESULT_TEMPORARILY_REJECTED",
    "MAV_RESULT_UNSUPPORTED",
]


def ack(result: str, command: str = "MAV_CMD_PREFLIGHT_CALIBRATION") -> Dict[str, Any]:
    return {"type": "COMMAND_ACK", "command": {"type": command}, "result": {"type": result}}


def replay(state: GyroBaroState, messages: List[Dict[str, Any]]) -> GyroBaroState:
    for message in messages:
        state, commands = on_message(state, message)
        assert not commands
    return state


@pytest.mark.parametrize("kind", [PreflightCalibration.GYROSCOPE, PreflightCalibration.BAROMETER])
def test_one_command_one_ack(kind: PreflightCalibration) -> None:
    state, commands = start(kind)
    assert [command.command for command in commands] == ["MAV_CMD_PREFLIGHT_CALIBRATION"]
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [ack("MAV_RESULT_ACCEPTED")])
    assert state.status == CalibrationStatus.DONE
    assert state.reason is None
    assert not state.reboot_required


@pytest.mark.parametrize(
    "kind, param, value",
    [
        (PreflightCalibration.GYROSCOPE, 1, 1),
        (PreflightCalibration.BAROMETER, 3, 1),
        (PreflightCalibration.ACCELEROMETER, 5, 1),
        (PreflightCalibration.BOARD_LEVEL, 5, 2),
        (PreflightCalibration.SIMPLE_ACCELEROMETER, 5, 4),
    ],
)
def test_preflight_params_match_the_frontend(kind: PreflightCalibration, param: int, value: float) -> None:
    params = preflight_command(kind).params
    assert len(params) == 7
    assert {index + 1: param_value for index, param_value in enumerate(params) if param_value} == {param: value}


def test_accelerometer_kinds_are_not_gyro_baro() -> None:
    with pytest.raises(ValueError):
        start(PreflightCalibration.ACCELEROMETER)


@pytest.mark.parametrize("result", [*FAILURES, "MAV_RESULT_COMMAND_INT_ONLY"])
def test_non_accepted_ack_fails(result: str) -> None:
    state, _ = start(PreflightCalibration.GYROSCOPE)
    state = replay(state, [ack(result)])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason is not None and result in state.reason


def test_in_progress_keeps_running() -> None:
    state, _ = start(PreflightCalibration.BAROMETER)
    state = replay(state, [ack("MAV_RESULT_IN_PROGRESS"), ack("MAV_RESULT_IN_PROGRESS")])
    assert state.status == CalibrationStatus.RUNNING
    assert replay(state, [ack("MAV_RESULT_ACCEPTED")]).status == CalibrationStatus.DONE


def test_ack_of_another_command_is_ignored() -> None:
    state, _ = start(PreflightCalibration.GYROSCOPE)
    state = replay(
        state,
        [
            ack("MAV_RESULT_FAILED", "MAV_CMD_REQUEST_MESSAGE"),
            ack("MAV_RESULT_ACCEPTED", "MAV_CMD_DO_START_MAG_CAL"),
            {"type": "HEARTBEAT", "mavtype": {"type": "MAV_TYPE_SUBMARINE"}},
        ],
    )
    assert state.status == CalibrationStatus.RUNNING
    assert replay(state, [ack("MAV_RESULT_FAILED")]).status == CalibrationStatus.FAILED


def test_finished_calibration_ignores_late_acks() -> None:
    state, _ = start(PreflightCalibration.GYROSCOPE)
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), ack("MAV_RESULT_FAILED")])
    assert state.status == CalibrationStatus.DONE


def test_cancel_is_a_no_op() -> None:
    # ArduPilot can't cancel these; the calibration still ends with its ack
    state, _ = start(PreflightCalibration.BAROMETER)
    assert cancel(state) == (state, [])
    assert replay(state, [ack("MAV_RESULT_ACCEPTED")]).status == CalibrationStatus.DONE
