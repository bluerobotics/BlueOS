"""Calibrations that are one command, whose ack is the result."""

from typing import Any, Dict, List, Optional, Tuple

from calibration.ardupilot.preflight import ack_outcome, preflight_command
from pydantic import BaseModel
from vehicle_setup_types import FINISHED, CalibrationKind, CalibrationStatus, Command

FIXED_MAG_CAL_YAW = "MAV_CMD_FIXED_MAG_CAL_YAW"

PREFLIGHT_KINDS = (
    CalibrationKind.GYROSCOPE,
    CalibrationKind.BAROMETER,
    CalibrationKind.SIMPLE_ACCELEROMETER,
    CalibrationKind.BOARD_LEVEL,
)
NEEDS_REBOOT = (CalibrationKind.BOARD_LEVEL, CalibrationKind.LARGE_VEHICLE_COMPASS)


class SingleAckState(BaseModel):
    kind: CalibrationKind
    command: str
    status: CalibrationStatus = CalibrationStatus.RUNNING
    reason: Optional[str] = None
    reboot_required: bool = False


def start_preflight(kind: CalibrationKind) -> Tuple[SingleAckState, List[Command]]:
    if kind not in PREFLIGHT_KINDS:
        raise ValueError(f"{kind.value} doesn't end with its MAV_CMD_PREFLIGHT_CALIBRATION ack")

    command = preflight_command(kind)
    return SingleAckState(kind=kind, command=command.command), [command]


def start_large_vehicle_compass(
    compass_mask: int, latitude: float, longitude: float
) -> Tuple[SingleAckState, List[Command]]:
    # param1 0: the vehicle is pointing north
    command = Command(command=FIXED_MAG_CAL_YAW, params=[0, compass_mask, latitude, longitude])
    return SingleAckState(kind=CalibrationKind.LARGE_VEHICLE_COMPASS, command=FIXED_MAG_CAL_YAW), [command]


def on_message(state: SingleAckState, message: Dict[str, Any]) -> Tuple[SingleAckState, List[Command]]:
    outcome = ack_outcome(message, state.command)
    if state.status in FINISHED or outcome is None:
        return state, []

    status, reason = outcome
    reboot_required = status == CalibrationStatus.DONE and state.kind in NEEDS_REBOOT
    return state.model_copy(update={"status": status, "reason": reason, "reboot_required": reboot_required}), []


# ArduPilot has no MAVLink cancel for these; they end with their ack or the job's timeout
def cancel(state: SingleAckState) -> Tuple[SingleAckState, List[Command]]:
    return state, []
