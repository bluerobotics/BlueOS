import sys
from pathlib import Path
from typing import Any

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
