"""The pure parts with plain values, then calibration jobs run by the kernel with a stub autopilot link.

The stubs can't verify mavlink2rest's real websocket (its filter, framing, and what it does when the autopilot
reboots), the armed check and system id lookup, or how ArduPilot answers; that needs a SITL or vehicle check.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple, Union

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration.job import (
    Connect,
    Connected,
    Heard,
    LinkLost,
    Send,
    calibrate,
    on_message,
    snapshot,
    start_calibration,
    timeout_for,
)
from changesets.runner import VEHICLE_WRITE_LOCK
from job_list.job import Cancel, Io, Refused, TimedOut
from job_list.kernel import Kernel, UnknownJob
from pydantic import ValidationError
from vehicle_setup_types import (
    CalibrationKind,
    CalibrationStatus,
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
        {"calibration": "magnetometer"},
    ],
)
def test_bad_start_requests(body: Dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        StartCalibration(**body)


@pytest.mark.parametrize(
    "request_, command",
    [
        (StartCalibration(calibration=CalibrationKind.GYROSCOPE), "MAV_CMD_PREFLIGHT_CALIBRATION"),
        (StartCalibration(calibration=CalibrationKind.BOARD_LEVEL), "MAV_CMD_PREFLIGHT_CALIBRATION"),
        (StartCalibration(calibration=CalibrationKind.COMPASS, compass_mask=3), "MAV_CMD_DO_START_MAG_CAL"),
        (
            StartCalibration(
                calibration=CalibrationKind.LARGE_VEHICLE_COMPASS, compass_mask=1, latitude=-27.6, longitude=-48.5
            ),
            "MAV_CMD_FIXED_MAG_CAL_YAW",
        ),
    ],
)
def test_start_calibration_dispatches(request_: StartCalibration, command: str) -> None:
    state, commands = start_calibration(request_)
    assert state.status == CalibrationStatus.RUNNING
    assert [sent.command for sent in commands] == [command]


def test_compass_snapshot_progress_and_fitness() -> None:
    state, _ = start_calibration(StartCalibration(calibration=CalibrationKind.COMPASS, compass_mask=0b11))
    assert snapshot("1", CalibrationKind.COMPASS, state).progress == 0
    for message in (mag_progress(0, 40), mag_progress(1, 20)):
        state, _ = on_message(state, message)
    assert snapshot("1", CalibrationKind.COMPASS, state).progress == 30
    state, _ = on_message(state, mag_report(0, 12.5))
    current = snapshot("1", CalibrationKind.COMPASS, state)
    assert (current.job_id, current.progress, current.fitness, current.position) == ("1", 60, {0: 12.5}, None)


def test_timeouts_only_while_running() -> None:
    compass_timeout = timeout_for(CalibrationKind.COMPASS, CalibrationStatus.RUNNING)
    gyro_timeout = timeout_for(CalibrationKind.GYROSCOPE, CalibrationStatus.RUNNING)
    assert compass_timeout is not None and gyro_timeout is not None and compass_timeout > gyro_timeout
    for status in CalibrationStatus:
        if status != CalibrationStatus.RUNNING:
            assert timeout_for(CalibrationKind.ACCELEROMETER, status) is None


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
            raise ConnectionError("mavlink2rest is down")
        self.requests.append(request)
        return Connected() if isinstance(request, Connect) else None

    def sent(self) -> List[str]:
        return [request.command.command for request in self.requests if isinstance(request, Send)]


class FakeBus:
    def __init__(self, failing: bool = False) -> None:
        self.failing = failing
        self.published: List[Tuple[str, Any]] = []

    def publish(self, name: str, payload: Any) -> None:
        if self.failing:
            raise ConnectionError("the bus is down")
        if name != "jobs":
            self.published.append((name, payload))

    @property
    def calibrations(self) -> List[Dict[str, Any]]:
        return [payload for _, payload in self.published if payload is not None]


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


class Vehicle:
    def __init__(self, armed: Union[bool, Exception] = False, link: Optional[StubLink] = None, **bus: Any) -> None:
        self.armed = armed
        self.link = link or StubLink()
        self.bus = FakeBus(**bus)
        self.kernel = Kernel(self.bus, {"Calibrate": calibrate(self.link.scope, self.is_armed)})
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
async def test_lock_held_elsewhere_is_refused() -> None:
    await VEHICLE_WRITE_LOCK.acquire()
    try:
        with pytest.raises(Refused):
            await Vehicle().start(calibration="gyroscope")
    finally:
        VEHICLE_WRITE_LOCK.release()


@pytest.mark.asyncio
@pytest.mark.parametrize("armed", [True, ConnectionError("mavlink2rest is down")])
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
    assert (vehicle.last()["status"], vehicle.last()["reason"]) == ("failed", "timed out")
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
    assert vehicle.last()["reason"] == "could not reach the autopilot: mavlink2rest is down"
    assert vehicle.released()


@pytest.mark.asyncio
@pytest.mark.parametrize("waiting_for_position", [False, True])
async def test_a_lost_link_fails_the_job_at_once(waiting_for_position: bool) -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="accelerometer")
    if waiting_for_position:
        await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
        await vehicle.feed(vehicle_pos(1.0))
        assert vehicle.last()["status"] == "waiting_for_position"
    assert vehicle.link.deliver is not None
    vehicle.link.deliver(LinkLost("mavlink2rest's websocket closed"))
    await settle()
    assert vehicle.last()["status"] == "failed"
    assert vehicle.last()["reason"].startswith("lost the autopilot link: mavlink2rest's websocket closed")
    # Once ArduPilot has started the full calibration, only a reboot ends it on its side
    assert vehicle.last()["reboot_required"] == waiting_for_position
    assert vehicle.released()


@pytest.mark.asyncio
async def test_a_failing_bus_still_releases_the_job() -> None:
    vehicle = Vehicle(failing=True)
    await vehicle.start(calibration="barometer")
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
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
async def test_each_calibration_is_a_new_job() -> None:
    vehicle = Vehicle()
    await vehicle.start(calibration="gyroscope")
    first = vehicle.job_id
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_DENIED"))
    assert vehicle.last()["status"] == "failed" and vehicle.released()
    await vehicle.start(calibration="barometer")
    assert vehicle.job_id != first
    assert (vehicle.last()["job_id"], vehicle.last()["calibration"]) == (vehicle.job_id, "barometer")
    assert vehicle.bus.published[-1][0] == "calibration/barometer"
    await vehicle.feed(ack("MAV_CMD_PREFLIGHT_CALIBRATION", "MAV_RESULT_ACCEPTED"))
    assert vehicle.released()


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
