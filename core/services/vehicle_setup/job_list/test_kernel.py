"""The kernel with a fake bus and fake IO: plain jobs that publish, ask for IO, and react to what they're given."""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, List, Optional, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_list.job import (
    Cancel,
    Deadline,
    Done,
    Io,
    IoFailed,
    JobKind,
    JobRef,
    Publish,
    Refused,
    TimedOut,
)
from job_list.kernel import Kernel, UnknownJob
from pydantic import BaseModel

SHORT_DEADLINE = 0.01


class Step(BaseModel):
    value: str


class Finish(JobRef):
    pass


class FakeJob:
    def __init__(self, job_id: str, command: Any) -> None:
        self.job_id = job_id
        self.command = command
        self.events: List[Any] = []

    def start(self) -> List[Any]:
        return [Publish(Step(value="started")), "ping", Deadline(SHORT_DEADLINE if self.command == "short" else 5)]

    def handle(self, event: Any) -> List[Any]:
        self.events.append(event)
        if isinstance(event, (Finish, TimedOut, IoFailed)):
            return [Publish(Step(value=type(event).__name__)), Done()]
        if isinstance(event, Cancel):
            return []  # this job refuses to be cancelled
        if event == "pushed":
            return [Publish(Step(value="pushed")), Deadline(None)]
        if event == "broken":
            raise RuntimeError("bug")
        return []

    def failed(self, error: str) -> List[Any]:
        if self.command == "broken hook":
            raise RuntimeError("worse bug")
        return [Publish(Step(value=f"failed: {error}")), "ping", Deadline(5), Done()]


class FakeBus:
    def __init__(self, failing: bool = False) -> None:
        self.failing = failing
        self.published: List[Tuple[str, Any]] = []

    def publish(self, name: str, payload: Any) -> None:
        if self.failing:
            raise ConnectionError("the bus is down")
        self.published.append((name, payload))

    def last(self, name: str) -> Any:
        return [payload for published, payload in self.published if published == name][-1]


class FakeLink:
    def __init__(self, failing: bool = False, failing_close: bool = False) -> None:
        self.failing = failing
        self.failing_close = failing_close
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
        if self.failing_close:
            raise ConnectionError("the link broke while closing")

    async def run(self, request: Any) -> Any:
        if self.failing:
            raise ConnectionError("the link is down")
        self.requests.append(request)
        return f"{request} answered"


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


class Setup:
    def __init__(self, bus: Optional[FakeBus] = None, link: Optional[FakeLink] = None) -> None:
        self.bus = bus or FakeBus()
        self.link = link or FakeLink()
        self.limit = asyncio.Lock()
        self.jobs: List[FakeJob] = []
        kind = JobKind(create=self.create, io=self.link.scope, states=["step"], limit=self.limit)
        self.kernel = Kernel(self.bus, {"Run": kind})

    def create(self, job_id: str, command: Any) -> FakeJob:
        job = FakeJob(job_id, command)
        self.jobs.append(job)
        return job

    def released(self) -> bool:
        return not self.limit.locked() and not self.link.open and not self.kernel.running

    def listed(self) -> List[str]:
        return [job["job_id"] for job in self.bus.last("jobs")]


@pytest.mark.asyncio
async def test_a_job_runs_publishes_and_finishes() -> None:
    setup = Setup()
    assert setup.bus.published == [("jobs", []), ("step", None)]
    started = await setup.kernel.submit("Run", "go")
    await settle()
    assert setup.bus.published[2] == ("jobs", [{"job_id": started.job_id, "job": "Run"}])
    assert setup.bus.last("jobs") == [{"job_id": started.job_id, "job": "Run"}]
    assert setup.bus.last("step") == {"value": "started"}
    assert setup.link.requests == ["ping"] and setup.jobs[0].events == ["ping answered"]
    assert setup.limit.locked() and setup.link.open

    setup.kernel.signal(Finish(job_id=started.job_id))
    await settle()
    assert setup.bus.last("step") == {"value": "Finish"}
    assert setup.bus.last("jobs") == [] and setup.released()
    with pytest.raises(UnknownJob):
        setup.kernel.signal(Finish(job_id=started.job_id))


@pytest.mark.asyncio
async def test_state_is_published_only_when_it_changes() -> None:
    setup = Setup()
    started = await setup.kernel.submit("Run", "go")
    await settle()
    assert setup.link.deliver is not None
    count = len(setup.bus.published)
    setup.link.deliver("pushed")
    setup.link.deliver("pushed")
    await settle()
    assert setup.bus.published[count:] == [("step", {"value": "pushed"})]
    assert setup.jobs[0].events[-2:] == ["pushed", "pushed"]
    setup.kernel.signal(Finish(job_id=started.job_id))
    await settle()


@pytest.mark.asyncio
async def test_a_taken_limit_refuses() -> None:
    setup = Setup()
    first = await setup.kernel.submit("Run", "go")
    with pytest.raises(Refused):
        await setup.kernel.submit("Run", "again")
    assert len(setup.jobs) == 1 and setup.listed() == [first.job_id]
    setup.kernel.signal(Finish(job_id=first.job_id))
    await settle()
    assert setup.released()
    second = await setup.kernel.submit("Run", "again")
    assert setup.listed() == [second.job_id]
    await setup.kernel.stop()


@pytest.mark.asyncio
async def test_a_running_job_decides_about_cancel() -> None:
    setup = Setup()
    started = await setup.kernel.submit("Run", "go")
    await settle()
    assert setup.kernel.signal(Cancel(job_id=started.job_id)) == JobRef(job_id=started.job_id)
    await settle()
    assert setup.listed() == [started.job_id] and isinstance(setup.jobs[0].events[-1], Cancel)
    setup.kernel.signal(Finish(job_id=started.job_id))
    await settle()


@pytest.mark.asyncio
async def test_events_that_dont_rearm_the_deadline_dont_postpone_it() -> None:
    setup = Setup()
    await setup.kernel.submit("Run", "short")
    await settle()
    assert setup.link.deliver is not None
    for _ in range(6):
        setup.link.deliver("noise")
        await asyncio.sleep(SHORT_DEADLINE / 2)
    assert setup.bus.last("step") == {"value": "TimedOut"} and setup.released()


@pytest.mark.asyncio
async def test_a_disarmed_deadline_never_times_out() -> None:
    setup = Setup()
    started = await setup.kernel.submit("Run", "short")
    await settle()
    assert setup.link.deliver is not None
    setup.link.deliver("pushed")
    await asyncio.sleep(SHORT_DEADLINE * 3)
    assert setup.listed() == [started.job_id] and not any(isinstance(e, TimedOut) for e in setup.jobs[0].events)
    setup.kernel.signal(Finish(job_id=started.job_id))
    await settle()


@pytest.mark.asyncio
async def test_failing_io_and_bus_never_leak_the_limit() -> None:
    setup = Setup(bus=FakeBus(failing=True), link=FakeLink(failing=True))
    await setup.kernel.submit("Run", "go")
    await settle()
    event = setup.jobs[0].events[0]
    assert isinstance(event, IoFailed) and (event.request, event.error) == ("ping", "the link is down")
    assert setup.released()


@pytest.mark.asyncio
@pytest.mark.parametrize("command, last", [("go", {"value": "failed: bug"}), ("broken hook", {"value": "started"})])
async def test_a_raising_job_publishes_only_what_failed_returns(command: str, last: Any) -> None:
    setup = Setup()
    await setup.kernel.submit("Run", command)
    await settle()
    assert setup.link.deliver is not None
    setup.link.deliver("broken")
    await settle()
    assert setup.bus.last("step") == last
    assert setup.link.requests == ["ping"] and setup.released()


@pytest.mark.asyncio
async def test_a_failing_io_close_after_done_keeps_the_final_state() -> None:
    setup = Setup(link=FakeLink(failing_close=True))
    started = await setup.kernel.submit("Run", "go")
    await settle()
    setup.kernel.signal(Finish(job_id=started.job_id))
    await settle()
    assert setup.bus.last("step") == {"value": "Finish"} and setup.released()


class TopicJob(FakeJob):
    def start(self) -> List[Any]:
        return [Publish(Step(value="a"), topic="a"), Publish(Step(value="b")), Publish(Step(value="c"), topic="c")]


@pytest.mark.asyncio
async def test_publish_goes_to_one_of_the_kinds_states() -> None:
    bus, link = FakeBus(), FakeLink()
    kernel = Kernel(bus, {"Run": JobKind(create=TopicJob, io=link.scope, states=["a", "b"])})
    assert bus.published == [("jobs", []), ("a", None), ("b", None)]
    await kernel.submit("Run", "go")
    await settle()
    assert [name for name, _ in bus.published if name != "jobs"] == ["a", "b", "a"]
    assert bus.last("a") == {"value": "a"} and bus.last("b") is None
    await kernel.stop()


@pytest.mark.asyncio
async def test_a_failed_precondition_releases_the_limit() -> None:
    async def refuse() -> None:
        raise Refused("no")

    bus, link, limit = FakeBus(), FakeLink(), asyncio.Lock()
    kernel = Kernel(bus, {"Run": JobKind(create=FakeJob, io=link.scope, limit=limit, precondition=refuse)})
    with pytest.raises(Refused):
        await kernel.submit("Run", "go")
    assert not limit.locked() and not kernel.running and bus.last("jobs") == [] and not link.open


@pytest.mark.asyncio
async def test_stop_cancels_every_job() -> None:
    bus, link = FakeBus(), FakeLink()
    kernel = Kernel(bus, {"Run": JobKind(create=FakeJob, io=link.scope, states=["step"])})
    await kernel.submit("Run", "go")
    await kernel.submit("Run", "again")
    await settle()
    assert len(bus.last("jobs")) == 2
    await kernel.stop()
    assert bus.last("jobs") == [] and not kernel.running and not link.open
