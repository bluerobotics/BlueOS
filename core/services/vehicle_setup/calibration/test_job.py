"""The pure parts with plain values, then calibration jobs run by the kernel with a stub autopilot link.

The stubs can't verify mavlink-server's real zenoh topics (what they carry when the autopilot reboots or zenohd
restarts), the armed check and system id lookup, or how ArduPilot answers; that needs a SITL or vehicle check.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple, Union

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration import ardupilot
from calibration.job import (
    VEHICLE_WRITE_LOCK,
    Connect,
    Connected,
    Heard,
    Send,
    calibrate,
)
from commonwealth.jobs.job import Cancel, Io, Refused, TimedOut
from commonwealth.jobs.kernel import Kernel, UnknownJob
from pydantic import ValidationError
from vehicle_setup_types import (
    CalibrationKind,
    ConfirmPosition,
    PoseKey,
    StartCalibration,
)


def ack(command: str, result: str) -> Dict[str, Any]:
    return {"type": "COMMAND_ACK", "command": {"type": command}, "result": {"type": result}}


def vehicle_pos(param1: float) -> Dict[str, Any]:
    return {"type": "COMMAND_LONG", "command": {"type": "MAV_CMD_ACCELCAL_VEHICLE_POS"}, "param1": param1}


def mag_progress(compass_id: int, completion_pct: int) -> Dict[str, Any]:
    return {"type": "MAG_CAL_PROGRESS", "compass_id": compass_id, "completion_pct": completion_pct}


def mag_report(compass_id: int, fitness: float) -> Dict[str, Any]:
    return {
        "type": "MAG_CAL_REPORT",
        "compass_id": compass_id,
        "cal_status": {"type": "MAG_CAL_SUCCESS"},
        "fitness": fitness,
    }


@pytest.mark.parametrize(
    "body",
    [
        {"calibration": "compass"},
        {"calibration": "compass", "compass_mask": 0},
        {"calibration": "large_vehicle_compass", "compass_mask": 1, "latitude": -27.6},
        {"calibration": "large_vehicle_compass", "compass_mask": 1, "latitude": 91, "longitude": 0},
    ],
)
def test_bad_start_requests(body: Dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        StartCalibration(**body)


def test_ardupilot_compass_snapshot_progress_and_fitness() -> None:
    state, _ = ardupilot.start(StartCalibration(calibration=CalibrationKind.COMPASS, compass_mask=0b11))
    assert ardupilot.snapshot("1", CalibrationKind.COMPASS, state).progress == 0
    for message in (mag_progress(0, 40), mag_progress(1, 20)):
        state, _ = ardupilot.on_message(state, message)
    assert ardupilot.snapshot("1", CalibrationKind.COMPASS, state).progress == 30
    state, _ = ardupilot.on_message(state, mag_report(0, 12.5))
    current = ardupilot.snapshot("1", CalibrationKind.COMPASS, state)
    assert (current.job_id, current.progress, current.fitness, current.position) == ("1", 60, {0: 12.5}, None)


class StubLink:
    def __init__(self, failing: Tuple[type, ...] = ()) -> None:
        self.failing = failing
        self.requests: List[Any] = []
        self.deliver: Optional[Callable[[Any], None]] = None
        self.open = False

    @asynccontextmanager
    async def scope(self, deliver: Callable[[Any], None]) -> AsyncIterator[Io]:
        self.deliver, self.open = deliver, True
        try:
            yield self.run
        finally:
            self.open = False

    async def run(self, request: Any) -> Any:
        if isinstance(request, self.failing):
            raise ConnectionError("mavlink-server is down")
        self.requests.append(request)
        return Connected() if isinstance(request, Connect) else None

    def sent(self) -> List[str]:
        return [request.command.command for request in self.requests if isinstance(request, Send)]


class FakeBus:
    def __init__(self) -> None:
        self.published: List[Tuple[str, Any]] = []

    def publish(self, name: str, payload: Any) -> None:
        if name != "jobs":
            self.published.append((name, payload))

    @property
    def calibrations(self) -> List[Dict[str, Any]]:
        return [payload for _, payload in self.published if payload is not None]


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


class Vehicle:
    def __init__(self, armed: Union[bool, Exception] = False, link: Optional[StubLink] = None) -> None:
        self.armed = armed
        self.link = link or StubLink()
        self.bus = FakeBus()
        self.kernel = Kernel(self.bus, {"Calibrate": calibrate(self.link.scope, self.is_armed, ardupilot)})
        self.job_id = ""

    async def is_armed(self) -> bool:
        if isinstance(self.armed, Exception):
            raise self.armed
        return self.armed

    async def start(self, **request: Any) -> None:
        self.job_id = (await self.kernel.submit("Calibrate", StartCalibration(**request))).job_id
        await settle()

    async def feed(self, message: Dict[str, Any]) -> None:
        assert self.link.deliver is not None and self.link.open, "not connected"
        self.link.deliver(Heard(message))
        await settle()

    async def signal(self, signal: Any) -> None:
        self.kernel.signal(signal)
        await settle()

    async def expire(self) -> None:
        assert self.link.deliver is not None
        self.link.deliver(TimedOut())
        await settle()

    def last(self) -> Dict[str, Any]:
        return self.bus.calibrations[-1]

    def statuses(self) -> List[str]:
        return [calibration["status"] for calibration in self.bus.calibrations]

    def armed_timer(self) -> bool:
        running = self.kernel.running.get(self.job_id)
        return running is not None and running.deadline is not None

    def released(self) -> bool:
        return not VEHICLE_WRITE_LOCK.locked() and not self.link.open and not self.kernel.running


@pytest.mark.asyncio
async def test_gyro() -> None:
    vehicle = Vehicle()
    assert vehicle.bus.published == [(f"calibration/{kind.value}", None) for kind in CalibrationKind]
    await vehicle.start(calibration="gyroscope")
    assert vehicle.bus.published[-1][0] == "calibration/gyroscope"
    assert isinstance(vehicle.link.requests[0], Connect)
    assert vehicle.link.sent() == ["MAV_CMD_PREFLIGHT_CALIBRATION"]
    assert vehicle.statuses() == ["running"] and vehicle.last()["job_id"] == vehicle.job_id
    assert VEHICLE_WRITE_LOCK.locked() and vehicle.armed_timer()

    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_IN_PROGRESS"))
    assert vehicle.statuses() == ["running"]
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
    assert vehicle.statuses() == ["running", "done"]
    assert vehicle.released()
    with pytest.raises(UnknownJob):
        vehicle.kernel.signal(ConfirmPosition(job_id=vehicle.job_id))


@pytest.mark.asyncio
async def test_busy_is_refused() -> None:
    first, second = Vehicle(), Vehicle()
    await first.start(calibration="barometer")
    with pytest.raises(Refused):
        await second.start(calibration="gyroscope")
    assert not second.link.requests and second.bus.calibrations == []
    await first.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
    assert first.released()


@pytest.mark.asyncio
@pytest.mark.parametrize("armed", [True, ConnectionError("mavlink-server is down")])
async def test_armed_or_unknown_is_refused(armed: Union[bool, Exception]) -> None:
    vehicle = Vehicle(armed)
    with pytest.raises(Refused):
        await vehicle.start(calibration="gyroscope")
    assert not vehicle.link.requests and vehicle.released()


@pytest.mark.asyncio
async def test_timeout_fails_the_job() -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="gyroscope")
    await vehicle.signal(Cancel(job_id=vehicle.job_id))
    assert vehicle.statuses() == ["running"] and VEHICLE_WRITE_LOCK.locked()
    await vehicle.expire()
    assert (vehicle.last()["status"], vehicle.last()["reason"], vehicle.last()["reboot_required"]) == (
        "failed",
        "timed out",
        False,
    )
    assert vehicle.released()


@pytest.mark.asyncio
async def test_no_timeout_while_waiting_for_a_position() -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="accelerometer")
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
    await vehicle.feed(vehicle_pos(1.0))
    assert not vehicle.armed_timer()
    await vehicle.expire()
    assert vehicle.last()["status"] == "waiting_for_position" and VEHICLE_WRITE_LOCK.locked()
    await vehicle.signal(ConfirmPosition(job_id=vehicle.job_id))
    assert vehicle.armed_timer()
    await vehicle.expire()
    assert vehicle.last()["status"] == "failed" and vehicle.released()


@pytest.mark.asyncio
@pytest.mark.parametrize("failing", [Connect, Send])
async def test_an_unreachable_autopilot_fails_the_job(failing: type) -> None:
    vehicle = Vehicle(link=StubLink(failing=(failing,)))
    await vehicle.start(calibration="gyroscope")
    assert vehicle.statuses() == ["running", "failed"]
    assert vehicle.last()["reason"] == "could not reach the autopilot: mavlink-server is down"
    assert vehicle.released()


@pytest.mark.asyncio
async def test_accelerometer_confirm_and_cancel() -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="accelerometer")
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
    await vehicle.feed(vehicle_pos(2.0))
    assert (vehicle.last()["status"], vehicle.last()["position"]) == ("waiting_for_position", PoseKey.LEFT.value)

    await vehicle.signal(ConfirmPosition(job_id=vehicle.job_id))
    await vehicle.signal(ConfirmPosition(job_id=vehicle.job_id))
    assert vehicle.last()["status"] == "running"
    assert vehicle.link.sent()[1:] == ["MAV_CMD_ACCELCAL_VEHICLE_POS"]
    sent = vehicle.link.requests[-1]
    assert isinstance(sent, Send) and sent.command.params == [2]

    await vehicle.signal(Cancel(job_id=vehicle.job_id))
    assert vehicle.last()["status"] == "cancelled"
    assert vehicle.last()["reason"] is not None and vehicle.last()["reboot_required"]
    assert vehicle.released()


@pytest.mark.asyncio
async def test_compass_cancel_waits_for_the_autopilot() -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="compass", compass_mask=1)
    await vehicle.feed(mag_progress(0, 50))
    assert vehicle.last()["progress"] == 50
    await vehicle.signal(Cancel(job_id=vehicle.job_id))
    assert vehicle.last()["status"] == "running"
    assert vehicle.link.sent() == ["MAV_CMD_DO_START_MAG_CAL", "MAV_CMD_DO_CANCEL_MAG_CAL"]
    assert VEHICLE_WRITE_LOCK.locked()
    await vehicle.feed(ack("MAV_CMD_DO_CANCEL_MAG_CAL", "MAV_RESULT_ACCEPTED"))
    assert vehicle.last()["status"] == "cancelled" and vehicle.released()


@pytest.mark.asyncio
async def test_a_raising_job_ends_failed() -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="accelerometer")
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
    await vehicle.feed(vehicle_pos(1.0))
    await vehicle.feed({"type": "COMMAND_ACK", "command": None})  # a malformed message the state machine trips on
    assert vehicle.bus.published[-1][0] == "calibration/accelerometer"
    assert vehicle.last()["status"] == "failed" and vehicle.last()["position"] == PoseKey.LEVEL.value
    assert vehicle.last()["reason"].startswith("internal error: ") and vehicle.last()["job_id"] == vehicle.job_id
    assert vehicle.released()
