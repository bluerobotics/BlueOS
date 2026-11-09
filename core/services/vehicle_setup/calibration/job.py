from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union

from calibration import accelerometer, compass, gyro_baro
from calibration.accelerometer import AccelerometerState
from calibration.compass import CompassState
from calibration.gyro_baro import GyroBaroState, PreflightCalibration
from changesets.runner import VEHICLE_WRITE_LOCK
from job_list.job import (
    Cancel,
    Deadline,
    Done,
    IoFailed,
    IoScope,
    JobKind,
    Publish,
    Refused,
    TimedOut,
)
from loguru import logger
from vehicle_setup_types import (
    FINISHED,
    CalibrationKind,
    CalibrationSession,
    CalibrationStatus,
    Command,
    ConfirmPosition,
    StartCalibration,
)

State = Union[GyroBaroState, AccelerometerState, CompassState]

# A late ack from a timed-out run can be read by the next job of the same command
TIMEOUTS: Dict[CalibrationKind, float] = {**dict.fromkeys(CalibrationKind, 30.0), CalibrationKind.COMPASS: 60.0}


# IO requests and what the autopilot link delivers, run by clients/mavlink.py
@dataclass(frozen=True)
class Connect:
    pass


@dataclass(frozen=True)
class Connected:
    pass


@dataclass(frozen=True)
class Send:
    command: Command


@dataclass(frozen=True)
class Heard:
    message: Dict[str, Any]


@dataclass(frozen=True)
class LinkLost:
    reason: str


def start_calibration(request: StartCalibration) -> Tuple[State, List[Command]]:
    kind = request.calibration
    if kind in (CalibrationKind.GYROSCOPE, CalibrationKind.BAROMETER):
        return gyro_baro.start(PreflightCalibration(kind.value))
    if kind == CalibrationKind.COMPASS:
        if request.compass_mask is None:
            raise ValueError("compass needs compass_mask")
        return compass.start(request.compass_mask)
    if kind == CalibrationKind.LARGE_VEHICLE_COMPASS:
        if request.compass_mask is None or request.latitude is None or request.longitude is None:
            raise ValueError("large_vehicle_compass needs compass_mask, latitude and longitude")
        return compass.start_large_vehicle(request.compass_mask, request.latitude, request.longitude)
    return accelerometer.start(PreflightCalibration(kind.value))


def on_message(state: State, message: Dict[str, Any]) -> Tuple[State, List[Command]]:
    if isinstance(state, AccelerometerState):
        return accelerometer.on_message(state, message)
    if isinstance(state, CompassState):
        return compass.on_message(state, message)
    return gyro_baro.on_message(state, message)


def confirm(state: State) -> Tuple[State, List[Command]]:
    if isinstance(state, AccelerometerState):
        return accelerometer.confirm(state)
    return state, []


def cancel(state: State) -> Tuple[State, List[Command]]:
    if isinstance(state, AccelerometerState):
        return accelerometer.cancel(state)
    if isinstance(state, CompassState):
        return compass.cancel(state)
    return gyro_baro.cancel(state)


def snapshot(job_id: str, kind: CalibrationKind, state: State) -> CalibrationSession:
    return CalibrationSession(
        job_id=job_id,
        calibration=kind,
        status=state.status,
        position=state.position if isinstance(state, AccelerometerState) else None,
        progress=compass.progress(state) if isinstance(state, CompassState) else None,
        fitness=state.fitness if isinstance(state, CompassState) else {},
        reason=state.reason,
        reboot_required=state.reboot_required,
    )


# No timeout while waiting for a position: the user is handling the vehicle and can cancel
def timeout_for(kind: CalibrationKind, status: CalibrationStatus) -> Optional[float]:
    return TIMEOUTS[kind] if status == CalibrationStatus.RUNNING else None


def fail(state: State, reason: str) -> State:
    if isinstance(state, AccelerometerState):
        return accelerometer.abandon(state, reason)
    return state.model_copy(update={"status": CalibrationStatus.FAILED, "reason": reason})


def state_topic(kind: CalibrationKind) -> str:
    return f"calibration/{kind.value}"


class CalibrationJob:
    def __init__(self, job_id: str, request: StartCalibration) -> None:
        self.job_id = job_id
        self.kind = request.calibration
        self.state, self.commands = start_calibration(request)

    # The link opens before the first command, so no answer to it is missed
    def start(self) -> List[Any]:
        return [Connect(), *self.outputs(self.state, [], heard=True)]

    def handle(self, event: Any) -> List[Any]:
        state = self.state
        if state.status in FINISHED:
            return []
        commands: List[Command] = []
        match event:
            case Heard(message):
                return self.outputs(*on_message(state, message), heard=True)
            case Connected():
                commands, self.commands = self.commands, []
            case ConfirmPosition():
                state, commands = confirm(state)
            case Cancel():
                state, commands = cancel(state)
            case TimedOut() if state.status == CalibrationStatus.RUNNING:
                state = fail(state, "timed out")
            case IoFailed(error=error):
                state = fail(state, f"could not reach the autopilot: {error}")
            case LinkLost(reason):
                state = fail(state, f"lost the autopilot link: {reason}")
        return self.outputs(state, commands)

    def failed(self, error: str) -> List[Any]:
        return [self.publish(fail(self.state, f"internal error: {error}"))]

    def publish(self, state: State) -> Publish:
        return Publish(snapshot(self.job_id, self.kind, state), topic=state_topic(self.kind))

    # Any message from the autopilot restarts the timeout, so it only fires once it goes quiet
    def outputs(self, state: State, commands: List[Command], heard: bool = False) -> List[Any]:
        changed = state != self.state
        self.state = state
        outputs: List[Any] = [Send(command) for command in commands]
        outputs.append(self.publish(state))
        if state.status in FINISHED:
            outputs.append(Done())
        elif heard or changed:
            outputs.append(Deadline(timeout_for(self.kind, state.status)))
        return outputs


def calibrate(link: IoScope, is_armed: Callable[[], Awaitable[bool]]) -> JobKind:
    async def refuse_if_armed() -> None:
        try:
            armed = await is_armed()
        except Exception as error:
            logger.warning(f"Could not read the vehicle's armed state: {error!r}")
            raise Refused(f"could not read the vehicle's armed state: {error}") from error
        if armed:
            raise Refused("the vehicle is armed")

    return JobKind(
        create=CalibrationJob,
        io=link,
        states=[state_topic(kind) for kind in CalibrationKind],
        limit=VEHICLE_WRITE_LOCK,
        precondition=refuse_if_armed,
    )
