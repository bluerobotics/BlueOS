import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from calibration.ardupilot.full_accelerometer import (
    FullAccelerometerState,
    abandon,
    cancel,
    confirm,
    on_message,
    start,
)
from vehicle_setup_types import CalibrationStatus, PoseKey


def ack(result: str, command: str = "MAV_CMD_PREFLIGHT_CALIBRATION") -> Dict[str, Any]:
    return {"type": "COMMAND_ACK", "command": {"type": command}, "result": {"type": result}}


def vehicle_pos(param1: float) -> Dict[str, Any]:
    return {
        "type": "COMMAND_LONG",
        "command": {"type": "MAV_CMD_ACCELCAL_VEHICLE_POS"},
        "param1": param1,
        "param2": 0.0,
        "param3": 0.0,
        "param4": 0.0,
        "param5": 0.0,
        "param6": 0.0,
        "param7": 0.0,
        "target_system": 255,
        "target_component": 0,
        "confirmation": 0,
    }


def replay(state: FullAccelerometerState, messages: List[Dict[str, Any]]) -> FullAccelerometerState:
    for message in messages:
        state, commands = on_message(state, message)
        assert not commands
    return state


def started() -> FullAccelerometerState:
    state, commands = start()
    assert [(command.command, command.params[4]) for command in commands] == [("MAV_CMD_PREFLIGHT_CALIBRATION", 1)]
    return state


@pytest.mark.parametrize("acked, reboot_required", [(True, True), (False, False)])
def test_abandoning_leaves_only_a_started_calibration_open(acked: bool, reboot_required: bool) -> None:
    state = started()
    if acked:
        state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(1.0)])
    abandoned = abandon(state, "timed out")
    assert abandoned.status == CalibrationStatus.FAILED and abandoned.reboot_required == reboot_required
    assert abandoned.reason is not None and abandoned.reason.startswith("timed out")
    assert ("until the autopilot reboots" in abandoned.reason) == reboot_required


def test_full_six_position_conversation() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_ACCEPTED")])
    assert state.status == CalibrationStatus.RUNNING
    for number, pose in enumerate(PoseKey, start=1):
        state = replay(state, [vehicle_pos(float(number))])
        assert (state.status, state.position) == (CalibrationStatus.WAITING_FOR_POSITION, pose)
        state, commands = confirm(state)
        assert state.status == CalibrationStatus.RUNNING
        assert [(command.command, command.params[0]) for command in commands] == [
            ("MAV_CMD_ACCELCAL_VEHICLE_POS", number)
        ]
        # the autopilot's ack to our confirmation is not the calibration's result
        state = replay(state, [ack("MAV_RESULT_ACCEPTED", "MAV_CMD_ACCELCAL_VEHICLE_POS")])
        assert state.status == CalibrationStatus.RUNNING
    state = replay(state, [vehicle_pos(16777215.0)])
    assert state.status == CalibrationStatus.DONE
    assert state.position is None


def test_full_ignores_the_last_runs_result_before_the_start_ack() -> None:
    # ArduPilot keeps broadcasting the previous calibration's result until it handles the new start
    state = started()
    state = replay(state, [vehicle_pos(16777215.0), vehicle_pos(16777216.0), vehicle_pos(3.0)])
    assert (state.status, state.position) == (CalibrationStatus.RUNNING, None)
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(1.0)])
    assert (state.status, state.position) == (CalibrationStatus.WAITING_FOR_POSITION, PoseKey.LEVEL)


def test_full_lost_confirmation_is_offered_again() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(1.0)])
    state, first = confirm(state)
    state = replay(state, [vehicle_pos(1.0)])
    assert (state.status, state.position) == (CalibrationStatus.RUNNING, PoseKey.LEVEL)
    state = replay(state, [vehicle_pos(1.0)])
    assert (state.status, state.position) == (CalibrationStatus.WAITING_FOR_POSITION, PoseKey.LEVEL)
    assert state.reason is not None
    state, again = confirm(state)
    assert again == first
    state = replay(state, [vehicle_pos(1.0), vehicle_pos(2.0)])
    assert (state.status, state.position, state.reason) == (CalibrationStatus.WAITING_FOR_POSITION, PoseKey.LEFT, None)


def test_rejected_confirmation_reason_survives_repeats() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(3.0)])
    state, _ = confirm(state)
    state = replay(
        state, [ack("MAV_RESULT_FAILED", "MAV_CMD_ACCELCAL_VEHICLE_POS"), vehicle_pos(3.0), vehicle_pos(3.0)]
    )
    assert (state.status, state.position) == (CalibrationStatus.WAITING_FOR_POSITION, PoseKey.RIGHT)
    assert state.reason is not None and "MAV_RESULT_FAILED" in state.reason


def test_full_autopilot_reports_failure() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(1.0)])
    state, _ = confirm(state)
    state = replay(state, [vehicle_pos(16777216.0)])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason is not None
    assert replay(state, [vehicle_pos(2.0)]).status == CalibrationStatus.FAILED


def test_full_start_refused() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_IN_PROGRESS"), ack("MAV_RESULT_TEMPORARILY_REJECTED")])
    assert state.status == CalibrationStatus.FAILED
    assert state.reason is not None and "MAV_RESULT_TEMPORARILY_REJECTED" in state.reason


def test_full_rejected_confirmation_can_be_confirmed_again() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(2.0)])
    state, first = confirm(state)
    state = replay(state, [ack("MAV_RESULT_FAILED", "MAV_CMD_ACCELCAL_VEHICLE_POS")])
    assert (state.status, state.position) == (CalibrationStatus.WAITING_FOR_POSITION, PoseKey.LEFT)
    assert state.reason is not None and "MAV_RESULT_FAILED" in state.reason
    state, again = confirm(state)
    assert again == first
    assert state.reason is None
    state = replay(state, [ack("MAV_RESULT_ACCEPTED", "MAV_CMD_ACCELCAL_VEHICLE_POS"), vehicle_pos(3.0)])
    assert (state.status, state.position, state.reason) == (CalibrationStatus.WAITING_FOR_POSITION, PoseKey.RIGHT, None)


def test_full_start_failure_clears_the_position() -> None:
    state = started()
    state = replay(state, [vehicle_pos(1.0), ack("MAV_RESULT_FAILED")])
    assert (state.status, state.position) == (CalibrationStatus.FAILED, None)


def test_full_ignores_unknown_positions_and_other_commands() -> None:
    state = started()
    unrelated = {**vehicle_pos(3.0), "command": {"type": "MAV_CMD_DO_SET_MODE"}}
    state = replay(
        state,
        [
            ack("MAV_RESULT_ACCEPTED"),
            vehicle_pos(0.0),
            vehicle_pos(7.0),
            unrelated,
            ack("MAV_RESULT_FAILED", "MAV_CMD_X"),
        ],
    )
    assert (state.status, state.position) == (CalibrationStatus.RUNNING, None)


def test_confirm_needs_a_requested_position() -> None:
    state = started()
    assert confirm(state) == (state, [])
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(2.0)])
    state, commands = confirm(state)
    assert len(commands) == 1
    assert confirm(state) == (state, [])


def test_full_cancel_is_local_and_honest() -> None:
    state = started()
    state = replay(state, [ack("MAV_RESULT_ACCEPTED"), vehicle_pos(4.0)])
    state, commands = cancel(state)
    assert (state.status, state.position, commands) == (CalibrationStatus.CANCELLED, None, [])
    assert state.reason is not None and state.reboot_required
    assert replay(state, [vehicle_pos(5.0)]).status == CalibrationStatus.CANCELLED
    assert confirm(state) == (state, [])
