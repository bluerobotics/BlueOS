import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from portwatcher import PortWatcher


@pytest.mark.asyncio
async def test_start_watching_continues_after_add_ping360_error() -> None:
    watcher = PortWatcher(probe_callback=AsyncMock(), found_callback=AsyncMock())
    calls = 0

    async def flaky_add_ping360() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyError("uap0")
        raise asyncio.CancelledError()

    with (
        patch.object(watcher, "add_ping360", side_effect=flaky_add_ping360),
        patch("portwatcher.serial.tools.list_ports.comports", return_value=[]),
        patch("portwatcher.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(asyncio.CancelledError):
            await watcher.start_watching()

    assert calls == 2
