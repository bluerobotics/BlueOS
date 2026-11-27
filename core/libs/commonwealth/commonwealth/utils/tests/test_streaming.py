import asyncio
from typing import AsyncGenerator

import pytest

from commonwealth.utils.streaming import idle_timeout, streamer

pytestmark = pytest.mark.asyncio


async def slow_items(delays: list[float]) -> AsyncGenerator[int, None]:
    for index, delay in enumerate(delays):
        await asyncio.sleep(delay)
        yield index


async def test_idle_timeout_passes_items_and_ends() -> None:
    assert [item async for item in idle_timeout(slow_items([0, 0, 0]), 1)] == [0, 1, 2]


async def test_idle_timeout_fires_after_idle_period() -> None:
    with pytest.raises(TimeoutError, match="No progress"):
        async for _ in idle_timeout(slow_items([0, 5]), 0.1):
            pass


async def test_idle_timeout_is_reset_by_activity() -> None:
    # Total time (0.4 s) exceeds the limit, but no single gap does
    assert len([item async for item in idle_timeout(slow_items([0.1] * 4), 0.25)]) == 4


async def test_idle_timeout_closes_inner_generator() -> None:
    closed = []

    async def inner() -> AsyncGenerator[int, None]:
        try:
            yield 0
            await asyncio.sleep(5)
            yield 1
        finally:
            closed.append(True)

    with pytest.raises(TimeoutError):
        async for _ in idle_timeout(inner(), 0.1):
            pass
    assert closed == [True]

    closed.clear()
    gen = idle_timeout(inner(), 1)
    await anext(gen)
    await gen.aclose()
    assert closed == [True]


async def test_streamer_heartbeats_stop_before_the_end_of_stream() -> None:
    async def pulls() -> AsyncGenerator[bytes, None]:
        for _ in range(2):
            await asyncio.sleep(0.05)
            yield b"pull"

    lines = [line async for line in streamer(pulls(), heartbeats=0.01)]
    assert any('"fragment": -1' in line for line in lines)
    assert '"fragment": 1' in lines[-1]
    assert not [task for task in asyncio.all_tasks() if "send_heartbeat" in repr(task)]
