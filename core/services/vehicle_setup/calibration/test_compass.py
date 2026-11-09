import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration.compass import (
    CompassState,
    cancel,
    on_message,
    start,
    start_large_vehicle,
)
from vehicle_setup_types import CalibrationStatus


def ack(command: str, result: str) -> Dict[str, Any]:
    return {"type": "COMMAND_ACK", "command": {"type": command}, "result": {"type": result}}


def progress(compass_id: int, completion_pct: int) -> Dict[str, Any]:
    return {
        "type": "MAG_CAL_PROGRESS",
        "compass_id": compass_id,
        "cal_mask": 0,
        "cal_status": {"type": "MAG_CAL_RUNNING_STEP_ONE"},
        "attempt": 1,
        "completion_pct": completion_pct,
    }


def report(compass_id: int, fitness: float, cal_status: str = "MAG_CAL_SUCCESS") -> Dict[str, Any]:
    return {
        "type": "MAG_CAL_REPORT",
        "compass_id": compass_id,
        "cal_mask": 0,
        "cal_status": {"type": cal_status},
        "autosaved": 1,
        "fitness": fitness,
    }


def replay(state: CompassState, messages: List[Dict[str, Any]]) -> CompassState:
    for message in messages:
        state, commands = on_message(state, message)
        assert not commands
    return state


def started(compass_mask: int) -> CompassState:
    state, commands = start(compass_mask)
    assert [(command.command, command.params) for command in commands] == [
        ("MAV_CMD_DO_START_MAG_CAL", [compass_mask, 0, 1])
    ]
    return replay(state, [ack("MAV_CMD_DO_START_MAG_CAL", "MAV_RESULT_ACCEPTED")])


def test_onboard_happy_path() -> None:
    state = started(0b101)
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [progress(0, 40), progress(2, 30), progress(0, 80), report(0, 12.5)])
    assert state.percent == {0: 80, 2: 30}
    assert state.fitness == {0: 12.5}
    assert state.status == CalibrationStatus.RUNNING
    assert not state.reboot_required
    state = replay(state, [progress(2, 100), report(2, 20.0)])
    assert state.fitness == {0: 12.5, 2: 20.0}
    assert state.status == CalibrationStatus.DONE
    assert state.reboot_required


def test_onboard_ignores_compasses_outside_the_mask() -> None:
    state = started(0b010)
    state = replay(state, [progress(0, 50), report(0, 10.0)])
    assert (state.percent, state.fitness, state.status) == ({}, {}, CalibrationStatus.RUNNING)
    state = replay(state, [report(1, 8.0)])
    assert state.status == CalibrationStatus.DONE


@pytest.mark.parametrize("cal_status", ["MAG_CAL_FAILED", "MAG_CAL_BAD_ORIENTATION", "MAG_CAL_BAD_RADIUS"])
def test_onboard_failed_report_fails_once_every_compass_reports(cal_status: str) -> None:
    state = started(0b011)
    state = replay(state, [report(1, 900.0, cal_status), report(1, 900.0, cal_status)])
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [report(0, 10.0)])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason == f"compass 1 answered {cal_status}"
    assert state.fitness == {0: 10.0, 1: 900.0}
    assert state.reboot_required
    assert replay(state, [report(1, 5.0)]).status == CalibrationStatus.FAILED


def test_onboard_every_compass_failing_needs_no_reboot() -> None:
    state = replay(started(0b011), [report(0, 900.0, "MAG_CAL_FAILED"), report(1, 900.0, "MAG_CAL_BAD_RADIUS")])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason == "compass 0 answered MAG_CAL_FAILED; compass 1 answered MAG_CAL_BAD_RADIUS"
    assert not state.reboot_required


@pytest.mark.parametrize("result", ["MAV_RESULT_DENIED", "MAV_RESULT_FAILED", "MAV_RESULT_TEMPORARILY_REJECTED"])
def test_onboard_start_refused(result: str) -> None:
    state, _ = start(0b001)
    state = replay(state, [ack("MAV_CMD_DO_START_MAG_CAL", "MAV_RESULT_IN_PROGRESS")])
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [ack("MAV_CMD_DO_START_MAG_CAL", result)])
    assert state.status == CalibrationStatus.FAILED
    assert replay(state, [report(0, 10.0)]).fitness == {}


def test_onboard_ignores_unrelated_messages() -> None:
    state = started(0b001)
    state = replay(
        state,
        [
            ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_FAILED"),
            ack("MAV_CMD_DO_CANCEL_MAG_CAL", "MAV_RESULT_ACCEPTED"),
            {"type": "STATUSTEXT", "severity": {"type": "MAV_SEVERITY_INFO"}, "text": []},
        ],
    )
    assert state.status == CalibrationStatus.RUNNING


def test_onboard_needs_a_compass() -> None:
    with pytest.raises(ValueError):
        start(0)


def test_cancel() -> None:
    state = replay(started(0b001), [progress(0, 50)])
    state, commands = cancel(state)
    assert [command.command for command in commands] == ["MAV_CMD_DO_CANCEL_MAG_CAL"]
    assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [ack("MAV_CMD_DO_CANCEL_MAG_CAL", "MAV_RESULT_ACCEPTED")])
    assert state.status == CalibrationStatus.CANCELLED
    assert not state.reboot_required
    assert cancel(state) == (state, [])
    assert replay(state, [report(0, 10.0)]).status == CalibrationStatus.CANCELLED


def test_cancel_refused_keeps_running() -> None:
    state, _ = cancel(started(0b001))
    state = replay(state, [ack("MAV_CMD_DO_CANCEL_MAG_CAL", "MAV_RESULT_DENIED")])
    assert state.status == CalibrationStatus.RUNNING
    assert state.reason is not None and "MAV_RESULT_DENIED" in state.reason
    state = replay(state, [report(0, 10.0)])
    assert state.status == CalibrationStatus.DONE
    assert state.reason is None


def test_cancel_accepted_after_a_refusal() -> None:
    state, _ = cancel(started(0b001))
    state = replay(state, [ack("MAV_CMD_DO_CANCEL_MAG_CAL", "MAV_RESULT_DENIED")])
    state, _ = cancel(state)
    state = replay(state, [ack("MAV_CMD_DO_CANCEL_MAG_CAL", "MAV_RESULT_ACCEPTED")])
    assert (state.status, state.reason) == (CalibrationStatus.CANCELLED, None)


def test_large_vehicle_keeps_coordinate_decimals() -> None:
    _, commands = start_large_vehicle(0b011, -27.5935, -48.5585)
    assert [(command.command, command.params) for command in commands] == [
        ("MAV_CMD_FIXED_MAG_CAL_YAW", [0, 0b011, -27.5935, -48.5585])
    ]


def test_large_vehicle_one_ack() -> None:
    state, _ = start_large_vehicle(0b001, -27.5935, -48.5585)
    state = replay(
        state,
        [
            ack("MAV_CMD_DO_START_MAG_CAL", "MAV_RESULT_FAILED"),
            report(0, 10.0),
            ack("MAV_CMD_FIXED_MAG_CAL_YAW", "MAV_RESULT_IN_PROGRESS"),
        ],
    )
    assert state.status == CalibrationStatus.RUNNING
    assert cancel(state) == (state, [])
    state = replay(state, [ack("MAV_CMD_FIXED_MAG_CAL_YAW", "MAV_RESULT_ACCEPTED")])
    assert state.status == CalibrationStatus.DONE
    assert state.reboot_required


def test_large_vehicle_refused() -> None:
    state, _ = start_large_vehicle(0b001, 0.0, 0.0)
    state = replay(state, [ack("MAV_CMD_FIXED_MAG_CAL_YAW", "MAV_RESULT_FAILED")])
    assert state.status == CalibrationStatus.FAILED
    assert not state.reboot_required
