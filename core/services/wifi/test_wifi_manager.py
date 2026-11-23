import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

_WIFI_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _WIFI_DIR)
_saved = {name: sys.modules.get(name) for name in ("exceptions", "settings", "typedefs")}
for name in _saved:
    sys.modules.pop(name, None)

from wifi_handlers.wpa_supplicant.WifiManager import WifiManager

for name, module in _saved.items():
    if module is not None:
        sys.modules[name] = module
    else:
        sys.modules.pop(name, None)

pytestmark = pytest.mark.asyncio


async def test_the_reconnect_watchdog_survives_wpa_supplicant_refusing_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = WifiManager.__new__(WifiManager)
    manager.connection_status = None  # type: ignore[assignment]
    manager._ignored_reconnection_networks = []
    manager._settings_manager = SimpleNamespace(settings=SimpleNamespace(smart_hotspot_enabled=False))  # type: ignore
    monkeypatch.setattr(manager, "get_current_network", AsyncMock(return_value=None))
    enable_saved_networks = AsyncMock(side_effect=RuntimeError("FAIL"))
    monkeypatch.setattr(manager, "enable_saved_networks", enable_saved_networks)
    monkeypatch.setattr(manager.wpa, "send_command_reconnect", AsyncMock(side_effect=RuntimeError("FAIL")))
    sleeps = 0

    async def fake_sleep(_seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        if sleeps == 4:
            raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await manager.auto_reconnect(0)

    # It went through the failing watchdog pass and kept looping
    enable_saved_networks.assert_awaited_once()
    assert sleeps == 4


async def test_reports_unavailable_without_a_socket() -> None:
    manager = WifiManager.__new__(WifiManager)

    assert (await manager.status()).state == "unavailable"
    assert await manager.get_wifi_available() == []
    assert await manager.get_saved_wifi_network() == []
    assert await manager.supports_hotspot() is False
    assert await manager.hotspot_is_running() is False


async def test_reports_available_after_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WifiManager.__new__(WifiManager)
    monkeypatch.setattr(manager.wpa, "run", lambda _target: None)
    monkeypatch.setattr(WifiManager, "get_wifi_available", _no_networks)

    # The udp socket is the fallback when there is no wpa_supplicant socket, it still means wifi works
    await manager.connect(("127.0.0.1", 6664))

    assert manager.wpa_path is not None


async def _no_networks(_self: Any) -> list[Any]:
    return []
