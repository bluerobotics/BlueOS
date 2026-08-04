import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

_PING_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _PING_DIR)
# Root pytest also finds other services' top-level modules (e.g. ardupilot_manager/exceptions.py).
for _name in ("exceptions", "pingutils", "ping360_ethernet_prober", "portwatcher"):
    _mod = sys.modules.get(_name)
    if _mod is not None and not str(getattr(_mod, "__file__", "")).startswith(_PING_DIR):
        del sys.modules[_name]

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
