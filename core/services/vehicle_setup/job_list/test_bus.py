"""The HTTP bus with plain queues, then its websocket handler with a fake socket.

The fake can't verify starlette's or uvicorn's real websocket behaviour, or nginx passing the upgrade through.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import WebSocketDisconnect
from job_list.bus import OUTBOX_SIZE, HttpBus
from job_list.job import Io, JobKind
from job_list.kernel import Kernel

NAME = "calibration/gyroscope"
TOPIC = f"vehicle-setup/state/{NAME}"


def frame(payload: Any) -> Dict[str, Any]:
    return {"topic": TOPIC, "payload": payload}


def drain(outbox: "asyncio.Queue[Dict[str, Any]]") -> List[Dict[str, Any]]:
    return [outbox.get_nowait() for _ in range(outbox.qsize())]


async def settle() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


class FakeSocket:
    def __init__(self, failing_send: bool = False, stuck: bool = False) -> None:
        self.failing_send = failing_send
        self.stuck = stuck
        self.incoming: "asyncio.Queue[Any]" = asyncio.Queue()
        self.sent: List[Dict[str, Any]] = []
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def accept(self) -> None:
        pass

    async def receive_json(self) -> Any:
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item

    async def send_json(self, data: Dict[str, Any]) -> None:
        if self.failing_send:
            raise RuntimeError("the client is gone")
        if self.stuck:
            await asyncio.Event().wait()
        self.sent.append(data)


@pytest.mark.asyncio
async def test_subscribe_gets_the_current_value_then_updates() -> None:
    bus = HttpBus("vehicle-setup")
    late: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    early: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    bus.subscribe(TOPIC, early)
    assert drain(early) == []
    bus.publish(NAME, {"status": "running"})
    bus.subscribe(TOPIC, late)
    assert drain(late) == drain(early) == [frame({"status": "running"})]
    assert bus.value(NAME) == {"status": "running"}

    bus.unsubscribe(TOPIC, early)
    bus.publish(NAME, {"status": "done"})
    assert drain(early) == [] and drain(late) == [frame({"status": "done"})]
    bus.unsubscribe(TOPIC, late)
    assert not bus.subscribers
    with pytest.raises(KeyError):
        bus.value("jobs")


@pytest.mark.asyncio
async def test_websocket_subscribe_unsubscribe_and_close() -> None:
    bus = HttpBus("vehicle-setup")
    bus.publish(NAME, {"status": "running"})
    socket = FakeSocket()
    serving = asyncio.create_task(bus.serve(socket))  # type: ignore[arg-type]
    socket.incoming.put_nowait("not a subscription")
    socket.incoming.put_nowait({"subscribe": TOPIC})
    await settle()
    assert socket.sent == [frame({"status": "running"})]
    bus.publish(NAME, {"status": "done"})
    await settle()
    socket.incoming.put_nowait({"unsubscribe": TOPIC})
    await settle()
    bus.publish(NAME, {"status": "failed"})
    socket.incoming.put_nowait({"subscribe": TOPIC})
    await settle()
    assert socket.sent == [frame({"status": status}) for status in ("running", "done", "failed")]

    socket.incoming.put_nowait(WebSocketDisconnect())
    await asyncio.wait_for(serving, 1)
    assert not bus.subscribers


@pytest.mark.asyncio
async def test_a_dead_websocket_is_dropped() -> None:
    bus = HttpBus("vehicle-setup")
    socket = FakeSocket(failing_send=True)
    serving = asyncio.create_task(bus.serve(socket))  # type: ignore[arg-type]
    socket.incoming.put_nowait({"subscribe": TOPIC})
    await settle()
    bus.publish(NAME, {"status": "running"})
    await asyncio.wait_for(serving, 1)
    assert not bus.subscribers


@pytest.mark.asyncio
async def test_a_client_that_stops_reading_is_dropped() -> None:
    bus = HttpBus("vehicle-setup")
    stuck, healthy = FakeSocket(stuck=True), FakeSocket()
    serving = [asyncio.create_task(bus.serve(socket)) for socket in (stuck, healthy)]  # type: ignore[arg-type]
    for socket in (stuck, healthy):
        socket.incoming.put_nowait({"subscribe": TOPIC})
    await settle()
    for count in range(OUTBOX_SIZE + 2):
        bus.publish(NAME, count)
        await asyncio.sleep(0)
    await asyncio.wait_for(serving[0], 1)
    assert stuck.closed and not serving[1].done() and len(bus.subscribers[TOPIC]) == 1
    bus.publish(NAME, "after")
    await settle()
    assert healthy.sent[-1] == frame("after") and len(healthy.sent) == OUTBOX_SIZE + 3
    healthy.incoming.put_nowait(WebSocketDisconnect())
    await asyncio.wait_for(serving[1], 1)
    assert not bus.subscribers


class ForeverJob:
    def __init__(self, job_id: str, _command: Any) -> None:
        self.job_id = job_id

    def start(self) -> List[Any]:
        return []

    def handle(self, _event: Any) -> List[Any]:
        return []

    def failed(self, _error: str) -> List[Any]:
        return []


@asynccontextmanager
async def no_io(deliver: Callable[[Any], None]) -> AsyncIterator[Io]:  # pylint: disable=unused-argument
    async def run(request: Any) -> Any:
        return request

    yield run


@pytest.mark.asyncio
async def test_closing_a_websocket_never_cancels_a_job() -> None:
    bus = HttpBus("vehicle-setup")
    kernel = Kernel(bus, {"Run": JobKind(create=ForeverJob, io=no_io)})
    socket = FakeSocket()
    serving = asyncio.create_task(bus.serve(socket))  # type: ignore[arg-type]
    socket.incoming.put_nowait({"subscribe": "vehicle-setup/state/jobs"})
    started = await kernel.submit("Run", None)
    await settle()
    socket.incoming.put_nowait(WebSocketDisconnect())
    await asyncio.wait_for(serving, 1)
    assert [job["job_id"] for job in bus.value("jobs")] == [started.job_id]
    assert socket.sent[-1]["payload"][0]["job_id"] == started.job_id
    await kernel.stop()
