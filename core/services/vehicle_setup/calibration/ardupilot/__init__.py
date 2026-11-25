"""ArduPilot's calibrations, as the Calibrator of calibration/job.py, grouped by how ArduPilot runs them."""

from typing import Any, Dict, List, Tuple, Union

from calibration.ardupilot import full_accelerometer, onboard_compass, single_ack
from calibration.ardupilot.full_accelerometer import FullAccelerometerState
from calibration.ardupilot.onboard_compass import OnboardCompassState
from calibration.ardupilot.single_ack import SingleAckState
from vehicle_setup_types import (
    CalibrationKind,
    CalibrationSession,
    CalibrationStatus,
    Command,
    StartCalibration,
)

State = Union[SingleAckState, FullAccelerometerState, OnboardCompassState]


def start(request: StartCalibration) -> Tuple[State, List[Command]]:
    match request.calibration:
        case CalibrationKind.ACCELEROMETER:
            return full_accelerometer.start()
        case CalibrationKind.COMPASS:
            if request.compass_mask is None:
                raise ValueError("compass needs compass_mask")
            return onboard_compass.start(request.compass_mask)
        case CalibrationKind.LARGE_VEHICLE_COMPASS:
            if request.compass_mask is None or request.latitude is None or request.longitude is None:
                raise ValueError("large_vehicle_compass needs compass_mask, latitude and longitude")
            return single_ack.start_large_vehicle_compass(request.compass_mask, request.latitude, request.longitude)
        case kind:
            return single_ack.start_preflight(kind)


def on_message(state: State, message: Dict[str, Any]) -> Tuple[State, List[Command]]:
    if isinstance(state, FullAccelerometerState):
        return full_accelerometer.on_message(state, message)
    if isinstance(state, OnboardCompassState):
        return onboard_compass.on_message(state, message)
    return single_ack.on_message(state, message)


def confirm(state: State) -> Tuple[State, List[Command]]:
    if isinstance(state, FullAccelerometerState):
        return full_accelerometer.confirm(state)
    return state, []


def cancel(state: State) -> Tuple[State, List[Command]]:
    if isinstance(state, FullAccelerometerState):
        return full_accelerometer.cancel(state)
    if isinstance(state, OnboardCompassState):
        return onboard_compass.cancel(state)
    return single_ack.cancel(state)


def abandon(state: State, reason: str) -> State:
    if isinstance(state, FullAccelerometerState):
        return full_accelerometer.abandon(state, reason)
    return state.model_copy(update={"status": CalibrationStatus.FAILED, "reason": reason})


def snapshot(job_id: str, kind: CalibrationKind, state: State) -> CalibrationSession:
    return CalibrationSession(
        job_id=job_id,
        calibration=kind,
        status=state.status,
        position=state.position if isinstance(state, FullAccelerometerState) else None,
        progress=onboard_compass.progress(state) if isinstance(state, OnboardCompassState) else None,
        fitness=state.fitness if isinstance(state, OnboardCompassState) else {},
        reason=state.reason,
        reboot_required=state.reboot_required,
    )
