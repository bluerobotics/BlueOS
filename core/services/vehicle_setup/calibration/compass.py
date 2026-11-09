from typing import Any, Dict, List, Optional, Tuple

from calibration.gyro_baro import ack_outcome
from pydantic import BaseModel
from vehicle_setup_types import FINISHED, CalibrationStatus, Command

START_MAG_CAL = "MAV_CMD_DO_START_MAG_CAL"
CANCEL_MAG_CAL = "MAV_CMD_DO_CANCEL_MAG_CAL"
FIXED_MAG_CAL_YAW = "MAV_CMD_FIXED_MAG_CAL_YAW"


class CompassState(BaseModel):
    command: str
    compass_mask: int
    status: CalibrationStatus = CalibrationStatus.RUNNING
    percent: Dict[int, float] = {}
    fitness: Dict[int, float] = {}
    results: Dict[int, Optional[str]] = {}
    cancelling: bool = False
    reason: Optional[str] = None
    reboot_required: bool = False


def _compass_ids(mask: int) -> List[int]:
    return [compass_id for compass_id in range(mask.bit_length()) if mask & (1 << compass_id)]


def start(compass_mask: int) -> Tuple[CompassState, List[Command]]:
    # MAVLink's 0 means every compass, which would leave us not knowing which reports to wait for
    if compass_mask <= 0:
        raise ValueError("compass_mask must select at least one compass")
    # param2 0: don't retry on failure, param3 1: save the calibration once it succeeds
    command = Command(command=START_MAG_CAL, params=[compass_mask, 0, 1])
    return CompassState(command=START_MAG_CAL, compass_mask=compass_mask), [command]


def start_large_vehicle(compass_mask: int, latitude: float, longitude: float) -> Tuple[CompassState, List[Command]]:
    # param1 0: the vehicle is pointing north
    command = Command(command=FIXED_MAG_CAL_YAW, params=[0, compass_mask, latitude, longitude])
    return CompassState(command=FIXED_MAG_CAL_YAW, compass_mask=compass_mask), [command]


def _on_ack(state: CompassState, message: Dict[str, Any]) -> CompassState:
    if state.cancelling and (outcome := ack_outcome(message, CANCEL_MAG_CAL)) is not None:
        status, reason = outcome
        if status == CalibrationStatus.DONE:
            return state.model_copy(update={"status": CalibrationStatus.CANCELLED, "cancelling": False, "reason": None})
        return state.model_copy(update={"cancelling": False, "reason": reason})
    outcome = ack_outcome(message, state.command)
    if outcome is None:
        return state
    status, reason = outcome
    if status == CalibrationStatus.DONE and state.command == START_MAG_CAL:
        return state
    return state.model_copy(
        update={"status": status, "reason": reason, "reboot_required": status == CalibrationStatus.DONE}
    )


def _on_report(state: CompassState, message: Dict[str, Any]) -> CompassState:
    compass_id = message.get("compass_id")
    compasses = _compass_ids(state.compass_mask)
    if compass_id not in compasses:
        return state
    fitness = {**state.fitness, compass_id: message.get("fitness", 0.0)}
    results = {**state.results, compass_id: message.get("cal_status", {}).get("type")}
    if set(results) != set(compasses):
        return state.model_copy(update={"fitness": fitness, "results": results})
    failures = [f"compass {key} answered {result}" for key, result in results.items() if result != "MAG_CAL_SUCCESS"]
    # ArduPilot autosaves each compass that succeeds, even when another one fails
    return state.model_copy(
        update={
            "status": CalibrationStatus.FAILED if failures else CalibrationStatus.DONE,
            "fitness": fitness,
            "results": results,
            "reason": "; ".join(failures) or None,
            "reboot_required": len(failures) < len(compasses),
        }
    )


def on_message(state: CompassState, message: Dict[str, Any]) -> Tuple[CompassState, List[Command]]:
    if state.status in FINISHED:
        return state, []
    if message.get("type") == "COMMAND_ACK":
        return _on_ack(state, message), []
    if state.command != START_MAG_CAL:
        return state, []
    if message.get("type") == "MAG_CAL_REPORT":
        return _on_report(state, message), []
    compass_id = message.get("compass_id")
    if message.get("type") == "MAG_CAL_PROGRESS" and compass_id in _compass_ids(state.compass_mask):
        return state.model_copy(update={"percent": {**state.percent, compass_id: message.get("completion_pct", 0)}}), []
    return state, []


def cancel(state: CompassState) -> Tuple[CompassState, List[Command]]:
    if state.status in FINISHED or state.command != START_MAG_CAL:
        return state, []
    return state.model_copy(update={"cancelling": True}), [Command(command=CANCEL_MAG_CAL, params=[])]


def progress(state: CompassState) -> Optional[float]:
    if state.command != START_MAG_CAL:
        return None
    compasses = _compass_ids(state.compass_mask)
    return sum(
        100.0 if compass_id in state.fitness else state.percent.get(compass_id, 0.0) for compass_id in compasses
    ) / len(compasses)
