from typing import Any, Dict, List, Optional, Tuple

from calibration.gyro_baro import (
    PREFLIGHT_CALIBRATION,
    PreflightCalibration,
    ack_outcome,
    preflight_command,
)
from pydantic import BaseModel
from vehicle_setup_types import FINISHED, CalibrationStatus, Command, PoseKey

ACCELCAL_VEHICLE_POS = "MAV_CMD_ACCELCAL_VEHICLE_POS"
ACCELCAL_VEHICLE_POS_SUCCESS = 16777215
ACCELCAL_VEHICLE_POS_FAILED = 16777216
POSES = tuple(PoseKey)

KINDS = (
    PreflightCalibration.ACCELEROMETER,
    PreflightCalibration.SIMPLE_ACCELEROMETER,
    PreflightCalibration.BOARD_LEVEL,
)


class AccelerometerState(BaseModel):
    kind: PreflightCalibration
    status: CalibrationStatus = CalibrationStatus.RUNNING
    position: Optional[PoseKey] = None
    reason: Optional[str] = None
    reboot_required: bool = False
    # ArduPilot rebroadcasts the last run's result every second, so positions only count after the start ack
    started: bool = False
    # At most one repeat of the confirmed position can be in flight, given ArduPilot's 1 s request interval
    repeat_ignored: bool = False


def start(kind: PreflightCalibration) -> Tuple[AccelerometerState, List[Command]]:
    if kind not in KINDS:
        raise ValueError(f"{kind} is not an accelerometer calibration")
    return AccelerometerState(kind=kind), [preflight_command(kind)]


def _on_ack(state: AccelerometerState, status: CalibrationStatus, reason: Optional[str]) -> AccelerometerState:
    # The full calibration's ack only says it started; the autopilot ends it with ACCELCAL_VEHICLE_POS
    if status == CalibrationStatus.DONE and state.kind == PreflightCalibration.ACCELEROMETER:
        return state.model_copy(update={"started": True})
    reboot_required = status == CalibrationStatus.DONE and state.kind == PreflightCalibration.BOARD_LEVEL
    return state.model_copy(
        update={"status": status, "position": None, "reason": reason, "reboot_required": reboot_required}
    )


def _on_position(state: AccelerometerState, position: int) -> AccelerometerState:
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


def on_message(state: AccelerometerState, message: Dict[str, Any]) -> Tuple[AccelerometerState, List[Command]]:
    if state.status in FINISHED:
        return state, []
    outcome = ack_outcome(message, PREFLIGHT_CALIBRATION)
    if outcome is not None:
        return _on_ack(state, *outcome), []
    if state.kind != PreflightCalibration.ACCELEROMETER:
        return state, []
    # The autopilot refuses a confirmation it wasn't waiting for; let the user confirm again
    confirmation = ack_outcome(message, ACCELCAL_VEHICLE_POS)
    if confirmation is not None and confirmation[0] == CalibrationStatus.FAILED and state.position is not None:
        return (
            state.model_copy(update={"status": CalibrationStatus.WAITING_FOR_POSITION, "reason": confirmation[1]}),
            [],
        )
    is_position = (
        message.get("type") == "COMMAND_LONG" and message.get("command", {}).get("type") == ACCELCAL_VEHICLE_POS
    )
    if is_position and state.started:
        return _on_position(state, int(message.get("param1", 0))), []
    return state, []


def confirm(state: AccelerometerState) -> Tuple[AccelerometerState, List[Command]]:
    if state.status != CalibrationStatus.WAITING_FOR_POSITION or state.position is None:
        return state, []
    command = Command(command=ACCELCAL_VEHICLE_POS, params=[POSES.index(state.position) + 1])
    return state.model_copy(update={"status": CalibrationStatus.RUNNING, "reason": None, "repeat_ignored": False}), [
        command
    ]


# ArduPilot has no MAVLink cancel for the full calibration (AP_AccelCal::cancel only runs on arming): it keeps
# waiting for a position until rebooted, so this only ends our job
def cancel(state: AccelerometerState) -> Tuple[AccelerometerState, List[Command]]:
    if state.status in FINISHED or state.kind != PreflightCalibration.ACCELEROMETER:
        return state, []
    reason = "ArduPilot can't cancel this calibration: it keeps waiting for a position until the autopilot reboots"
    update = {"status": CalibrationStatus.CANCELLED, "position": None, "reason": reason, "reboot_required": True}
    return state.model_copy(update=update), []


# Ending a run on our side (timeout, lost link, internal error) leaves a started full calibration open, as cancel does
def abandon(state: AccelerometerState, reason: str) -> AccelerometerState:
    update: Dict[str, Any] = {"status": CalibrationStatus.FAILED, "reason": reason}
    if state.kind == PreflightCalibration.ACCELEROMETER and state.started:
        update["reason"] = f"{reason}; ArduPilot keeps waiting for a position until the autopilot reboots"
        update["reboot_required"] = True
    return state.model_copy(update=update)
