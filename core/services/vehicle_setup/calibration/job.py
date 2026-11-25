import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Tuple

from commonwealth.jobs.job import (
    Cancel,
    Deadline,
    Done,
    Effect,
    IoFailed,
    IoRequest,
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

# Only one job writes to the vehicle at a time
VEHICLE_WRITE_LOCK = asyncio.Lock()

# A late ack from a timed-out run can be read by the next job of the same command
TIMEOUTS: Dict[CalibrationKind, float] = {**dict.fromkeys(CalibrationKind, 30.0), CalibrationKind.COMPASS: 60.0}


# IO requests and what the autopilot link delivers, run by clients/mavlink.py
@dataclass(frozen=True)
class Connect(IoRequest):
    pass


@dataclass(frozen=True)
class Connected:
    pass


@dataclass(frozen=True)
class Send(IoRequest):
    command: Command


@dataclass(frozen=True)
class Heard:
    message: Dict[str, Any]


class Calibrator(Protocol):
    def start(self, request: StartCalibration) -> Tuple[Any, List[Command]]:
        ...

    def on_message(self, state: Any, message: Dict[str, Any]) -> Tuple[Any, List[Command]]:
        ...

    def confirm(self, state: Any) -> Tuple[Any, List[Command]]:
        ...

    def cancel(self, state: Any) -> Tuple[Any, List[Command]]:
        ...

    # Ends the run on our side: timeout, unreachable autopilot or internal error
    def abandon(self, state: Any, reason: str) -> Any:
        ...

    def snapshot(self, job_id: str, kind: CalibrationKind, state: Any) -> CalibrationSession:
        ...


# No timeout while waiting for a position: the user is handling the vehicle and can cancel
def timeout_for(kind: CalibrationKind, status: CalibrationStatus) -> Optional[float]:
    return TIMEOUTS[kind] if status == CalibrationStatus.RUNNING else None


def state_topic(kind: CalibrationKind) -> str:
    return f"calibration/{kind.value}"


class CalibrationJob:
    def __init__(self, job_id: str, request: StartCalibration, calibrator: Calibrator) -> None:
        self.job_id = job_id
        self.calibrator = calibrator
        self.kind = request.calibration
        self.state, self.commands = calibrator.start(request)

    # The link opens before the first command, so no answer to it is missed
    def start(self) -> List[Effect]:
        return [Connect(), *self.effects(self.state, [], heard=True)]

    def handle(self, event: Any) -> List[Effect]:
        state = self.state
        if state.status in FINISHED:
            return []

        commands: List[Command] = []
        match event:
            case Heard(message):
                return self.effects(*self.calibrator.on_message(state, message), heard=True)
            case Connected():
                commands, self.commands = self.commands, []
            case ConfirmPosition():
                state, commands = self.calibrator.confirm(state)
            case Cancel():
                state, commands = self.calibrator.cancel(state)
            case TimedOut() if state.status == CalibrationStatus.RUNNING:
                state = self.calibrator.abandon(state, "timed out")
            case IoFailed(error=error):
                state = self.calibrator.abandon(state, f"could not reach the autopilot: {error}")
        return self.effects(state, commands)

    def failed(self, error: str) -> List[Effect]:
        return [self.publish(self.calibrator.abandon(self.state, f"internal error: {error}"))]

    def publish(self, state: Any) -> Publish:
        return Publish(self.calibrator.snapshot(self.job_id, self.kind, state), topic=state_topic(self.kind))

    # Any message from the autopilot restarts the timeout, so it only fires once it goes quiet
    def effects(self, state: Any, commands: List[Command], heard: bool = False) -> List[Effect]:
        changed = state != self.state
        self.state = state
        effects: List[Effect] = [Send(command) for command in commands]
        effects.append(self.publish(state))

        if state.status in FINISHED:
            effects.append(Done())
        elif heard or changed:
            effects.append(Deadline(timeout_for(self.kind, state.status)))

        return effects


def calibrate(link: IoScope, is_armed: Callable[[], Awaitable[bool]], calibrator: Calibrator) -> JobKind:
    async def refuse_if_armed() -> None:
        try:
            armed = await is_armed()
        except Exception as error:
            logger.warning(f"Could not read the vehicle's armed state: {error!r}")
            raise Refused(f"could not read the vehicle's armed state: {error}") from error
        if armed:
            raise Refused("the vehicle is armed")

    return JobKind(
        create=lambda job_id, request: CalibrationJob(job_id, request, calibrator),
        io=link,
        topics=[state_topic(kind) for kind in CalibrationKind],
        limit=VEHICLE_WRITE_LOCK,
        precondition=refuse_if_armed,
    )
