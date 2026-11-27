import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

_WIFI_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _WIFI_DIR)
_saved = {name: sys.modules.get(name) for name in ("exceptions", "settings", "typedefs")}
for name in _saved:
    sys.modules.pop(name, None)

from typedefs import WifiCredentials
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
    assert await manager.get_interfaces() == []
    assert await manager.hotspot_interface() is None


async def test_reports_available_after_connecting(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WifiManager.__new__(WifiManager)
    monkeypatch.setattr(manager.wpa, "run", lambda _target: None)
    monkeypatch.setattr(WifiManager, "get_wifi_available", _no_networks)

    # The udp socket is the fallback when there is no wpa_supplicant socket, it still means wifi works
    await manager.connect(("127.0.0.1", 6664))

    assert manager.wpa_path is not None
    assert await manager.get_interfaces() == ["wlan0"]


async def _no_networks(_self: Any, _interface: Any = None) -> list[Any]:
    return []


async def _connected_to(monkeypatch: pytest.MonkeyPatch, socket: str) -> WifiManager:
    manager = WifiManager.__new__(WifiManager)
    monkeypatch.setattr(manager.wpa, "run", lambda _target: None)
    monkeypatch.setattr(WifiManager, "get_wifi_available", _no_networks)
    await manager.connect(socket)
    monkeypatch.undo()
    return manager


async def test_uses_the_interface_of_the_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = await _connected_to(monkeypatch, "/var/run/wpa_supplicant/wlan1")

    assert await manager.get_interfaces() == ["wlan1"]
    assert await manager.hotspot_interface() == "wlan1"
    with patch("wifi_handlers.wpa_supplicant.WifiManager.subprocess.run") as run:
        manager.trigger_dhcp_client()
    run.assert_called_once_with(["dhcpcd", "-n", "wlan1"], check=False)


async def test_accepts_its_own_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = await _connected_to(monkeypatch, "/var/run/wpa_supplicant/wlan1")

    async def wpa_status() -> bytes:
        return b"wpa_state=COMPLETED\nssid=home"

    monkeypatch.setattr(manager.wpa, "send_command_status", wpa_status)
    status = await manager.status("wlan1")
    assert status.wpa_state == "COMPLETED"
    assert status.ssid == "home"
    await manager.set_hotspot_interface("wlan1")


@pytest.mark.parametrize(
    "operation",
    [
        lambda manager: manager.status("wlan0"),
        lambda manager: manager.get_wifi_available("wlan0"),
        lambda manager: manager.disconnect("wlan0"),
        lambda manager: manager.try_connect_to_network(WifiCredentials(ssid="home", password=""), interface="wlan0"),
        lambda manager: manager.set_hotspot_interface("wlan0"),
    ],
)
async def test_rejects_other_interfaces(monkeypatch: pytest.MonkeyPatch, operation: Any) -> None:
    manager = await _connected_to(monkeypatch, "/var/run/wpa_supplicant/wlan1")

    with pytest.raises(ValueError, match="'wlan0' not found"):
        await operation(manager)


async def test_rejects_any_interface_without_a_socket() -> None:
    manager = WifiManager.__new__(WifiManager)

    with pytest.raises(ValueError, match="'wlan0' not found"):
        await manager.status("wlan0")
