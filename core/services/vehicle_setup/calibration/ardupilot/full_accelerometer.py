"""The full accelerometer calibration: ArduPilot asks for six positions in turn, and the user confirms each one."""

from typing import Any, Dict, List, Optional, Tuple

from calibration.ardupilot.preflight import (
    PREFLIGHT_CALIBRATION,
    ack_outcome,
    preflight_command,
)
from pydantic import BaseModel
from vehicle_setup_types import (
    FINISHED,
    CalibrationKind,
    CalibrationStatus,
    Command,
    PoseKey,
)

ACCELCAL_VEHICLE_POS = "MAV_CMD_ACCELCAL_VEHICLE_POS"
ACCELCAL_VEHICLE_POS_SUCCESS = 16777215
ACCELCAL_VEHICLE_POS_FAILED = 16777216
POSES = tuple(PoseKey)


class FullAccelerometerState(BaseModel):
    status: CalibrationStatus = CalibrationStatus.RUNNING
    position: Optional[PoseKey] = None
    reason: Optional[str] = None
    reboot_required: bool = False
    # ArduPilot rebroadcasts the last run's result every second, so positions only count after the start ack
    started: bool = False
    # At most one repeat of the confirmed position can be in flight, given ArduPilot's 1 s request interval
    repeat_ignored: bool = False


def start() -> Tuple[FullAccelerometerState, List[Command]]:
    return FullAccelerometerState(), [preflight_command(CalibrationKind.ACCELEROMETER)]


# The ack only says it started; ArduPilot ends it with ACCELCAL_VEHICLE_POS
def _on_start_ack(
    state: FullAccelerometerState, status: CalibrationStatus, reason: Optional[str]
) -> FullAccelerometerState:
    if status == CalibrationStatus.DONE:
        return state.model_copy(update={"started": True})
    return state.model_copy(update={"status": status, "position": None, "reason": reason})


# The autopilot refuses a confirmation it wasn't waiting for; let the user confirm again
def _on_confirmation_answer(
    state: FullAccelerometerState, status: CalibrationStatus, reason: Optional[str]
) -> FullAccelerometerState:
    if status == CalibrationStatus.FAILED and state.position is not None:
        return state.model_copy(update={"status": CalibrationStatus.WAITING_FOR_POSITION, "reason": reason})
    return state


def _is_position_request(message: Dict[str, Any]) -> bool:
    return message.get("type") == "COMMAND_LONG" and message.get("command", {}).get("type") == ACCELCAL_VEHICLE_POS


def _on_position_request(state: FullAccelerometerState, position: int) -> FullAccelerometerState:
    if position == ACCELCAL_VEHICLE_POS_SUCCESS:
        return state.model_copy(update={"status": CalibrationStatus.DONE, "position": None, "reason": None})

    if position == ACCELCAL_VEHICLE_POS_FAILED:
        return state.model_copy(
            update={"status": CalibrationStatus.FAILED, "position": None, "reason": "autopilot reported failure"}
        )

    if not 1 <= position <= len(POSES):
        return state
    pose = POSES[position - 1]

    # ArduPilot repeats the request every second until it starts sampling the confirmed position
    if state.status == CalibrationStatus.RUNNING and state.position == pose:
        if not state.repeat_ignored:
            return state.model_copy(update={"repeat_ignored": True})
        lost = "the autopilot didn't receive the confirmation"
        return state.model_copy(update={"status": CalibrationStatus.WAITING_FOR_POSITION, "reason": lost})

    reason = state.reason if state.position == pose else None
    return state.model_copy(
        update={"status": CalibrationStatus.WAITING_FOR_POSITION, "position": pose, "reason": reason}
    )


def on_message(state: FullAccelerometerState, message: Dict[str, Any]) -> Tuple[FullAccelerometerState, List[Command]]:
    if state.status in FINISHED:
        return state, []
    if (start_ack := ack_outcome(message, PREFLIGHT_CALIBRATION)) is not None:
        return _on_start_ack(state, *start_ack), []
    if (answer := ack_outcome(message, ACCELCAL_VEHICLE_POS)) is not None:
        return _on_confirmation_answer(state, *answer), []
    if _is_position_request(message) and state.started:
        return _on_position_request(state, int(message.get("param1", 0))), []
    return state, []


# Tells the autopilot the vehicle is in the position it asked for
def confirm(state: FullAccelerometerState) -> Tuple[FullAccelerometerState, List[Command]]:
    if state.status != CalibrationStatus.WAITING_FOR_POSITION or state.position is None:
        return state, []

    command = Command(command=ACCELCAL_VEHICLE_POS, params=[POSES.index(state.position) + 1])
    confirmed = state.model_copy(update={"status": CalibrationStatus.RUNNING, "reason": None, "repeat_ignored": False})
    return confirmed, [command]


# ArduPilot has no MAVLink cancel for the full calibration (AP_AccelCal::cancel only runs on arming): it keeps
# waiting for a position until rebooted, so this only ends our job
def cancel(state: FullAccelerometerState) -> Tuple[FullAccelerometerState, List[Command]]:
    if state.status in FINISHED:
        return state, []

    reason = "ArduPilot can't cancel this calibration: it keeps waiting for a position until the autopilot reboots"
    update = {"status": CalibrationStatus.CANCELLED, "position": None, "reason": reason, "reboot_required": True}
    return state.model_copy(update=update), []


# Ending a run on our side (timeout, lost link, internal error) leaves a started calibration open
def abandon(state: FullAccelerometerState, reason: str) -> FullAccelerometerState:
    update: Dict[str, Any] = {"status": CalibrationStatus.FAILED, "reason": reason}
    if state.started:
        update["reason"] = f"{reason}; ArduPilot keeps waiting for a position until the autopilot reboots"
        update["reboot_required"] = True

    return state.model_copy(update=update)
