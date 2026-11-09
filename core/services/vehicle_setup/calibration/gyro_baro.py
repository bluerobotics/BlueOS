from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel
from vehicle_setup_types import FINISHED, CalibrationStatus, Command

PREFLIGHT_CALIBRATION = "MAV_CMD_PREFLIGHT_CALIBRATION"


class PreflightCalibration(str, Enum):
    GYROSCOPE = "gyroscope"
    BAROMETER = "barometer"
    ACCELEROMETER = "accelerometer"
    BOARD_LEVEL = "board_level"
    SIMPLE_ACCELEROMETER = "simple_accelerometer"


# https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_CALIBRATION
PREFLIGHT_PARAMS: Dict[PreflightCalibration, Tuple[float, ...]] = {
    PreflightCalibration.GYROSCOPE: (1, 0, 0, 0, 0, 0, 0),
    PreflightCalibration.BAROMETER: (0, 0, 1, 0, 0, 0, 0),
    PreflightCalibration.ACCELEROMETER: (0, 0, 0, 0, 1, 0, 0),
    PreflightCalibration.BOARD_LEVEL: (0, 0, 0, 0, 2, 0, 0),
    PreflightCalibration.SIMPLE_ACCELEROMETER: (0, 0, 0, 0, 4, 0, 0),
}

KINDS = (PreflightCalibration.GYROSCOPE, PreflightCalibration.BAROMETER)


class GyroBaroState(BaseModel):
    kind: PreflightCalibration
    status: CalibrationStatus = CalibrationStatus.RUNNING
    reason: Optional[str] = None
    reboot_required: bool = False


def preflight_command(kind: PreflightCalibration) -> Command:
    return Command(command=PREFLIGHT_CALIBRATION, params=list(PREFLIGHT_PARAMS[kind]))


def ack_outcome(message: Dict[str, Any], command: str) -> Optional[Tuple[CalibrationStatus, Optional[str]]]:
    """(status, failure reason) if `message` is the final COMMAND_ACK of `command`, None otherwise."""
    if message.get("type") != "COMMAND_ACK" or message.get("command", {}).get("type") != command:
        return None
    result = message.get("result", {}).get("type")
    if result == "MAV_RESULT_IN_PROGRESS":
        return None
    if result == "MAV_RESULT_ACCEPTED":
        return CalibrationStatus.DONE, None
    return CalibrationStatus.FAILED, f"{command} answered {result}"


def start(kind: PreflightCalibration) -> Tuple[GyroBaroState, List[Command]]:
    if kind not in KINDS:
        raise ValueError(f"{kind} is not a gyroscope or barometer calibration")
    return GyroBaroState(kind=kind), [preflight_command(kind)]


def on_message(state: GyroBaroState, message: Dict[str, Any]) -> Tuple[GyroBaroState, List[Command]]:
    outcome = ack_outcome(message, PREFLIGHT_CALIBRATION)
    if state.status in FINISHED or outcome is None:
        return state, []
    status, reason = outcome
    return state.model_copy(update={"status": status, "reason": reason}), []


# ArduPilot has no MAVLink cancel for these; they end with their ack or the session's timeout
def cancel(state: GyroBaroState) -> Tuple[GyroBaroState, List[Command]]:
    return state, []
