import sys
from pathlib import Path
from typing import Any, Iterator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_WIFI_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _WIFI_DIR)
_saved = {name: sys.modules.get(name) for name in ("exceptions", "settings", "typedefs", "main")}
for name in _saved:
    sys.modules.pop(name, None)

from fastapi.testclient import TestClient
from wifi_handlers.AbstractWifiHandler import AbstractWifiManager
from wifi_handlers.networkmanager.networkmanager import NetworkManagerWifi

# Importing main instantiates both handlers and sets up global logging, none of which should happen in tests
with (
    patch.object(AbstractWifiManager, "__init__", return_value=None),
    patch.object(NetworkManagerWifi, "__init__", return_value=None),
    patch("commonwealth.utils.logs.init_logger"),
    patch("logging.basicConfig"),
):
    import main
    from exceptions import InterfaceNotFound
    from typedefs import WifiCredentials, WifiStatus

for name, module in _saved.items():
    if module is not None:
        sys.modules[name] = module
    else:
        sys.modules.pop(name, None)

INTERFACES = ["wlan0", "wlan1"]


async def _validate_interface(interface: Optional[str]) -> None:
    if interface is not None and interface not in INTERFACES:
        raise InterfaceNotFound(interface)


@pytest.fixture(name="manager")
def fixture_manager(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    manager = MagicMock()
    manager.get_interfaces = AsyncMock(return_value=INTERFACES)
    manager.validate_interface = AsyncMock(side_effect=_validate_interface)
    manager.status = AsyncMock(
        side_effect=lambda interface: WifiStatus(interface=interface or "wlan0", state="connected")
    )
    manager.get_wifi_available = AsyncMock(return_value=[])
    manager.try_connect_to_network = AsyncMock()
    manager.disconnect = AsyncMock()
    manager.hotspot_interface = AsyncMock(return_value="wlan1")
    manager.set_hotspot_interface = AsyncMock()
    monkeypatch.setattr(main, "wifi_manager", manager)
    return manager


@pytest.fixture(name="client")
def fixture_client() -> Iterator[TestClient]:
    with TestClient(main.app) as client:
        yield client


def test_lists_interfaces(client: TestClient, manager: MagicMock) -> None:
    response = client.get("/v1.0/interfaces")
    assert response.status_code == 200
    assert response.json() == INTERFACES
    manager.get_interfaces.assert_awaited_once()


def test_status_without_interface_keeps_the_old_behavior(client: TestClient, manager: MagicMock) -> None:
    response = client.get("/v1.0/status")
    assert response.status_code == 200
    assert response.json()["interface"] == "wlan0"
    manager.status.assert_awaited_once_with(None)


def test_status_of_an_interface(client: TestClient, manager: MagicMock) -> None:
    response = client.get("/v1.0/status", params={"interface": "wlan1"})
    assert response.status_code == 200
    assert response.json()["interface"] == "wlan1"
    manager.status.assert_awaited_once_with("wlan1")


def test_scan_an_interface(client: TestClient, manager: MagicMock) -> None:
    response = client.get("/v1.0/scan", params={"interface": "wlan1"})
    assert response.status_code == 200
    manager.get_wifi_available.assert_awaited_once_with("wlan1")


def test_scan_without_interface(client: TestClient, manager: MagicMock) -> None:
    assert client.get("/v1.0/scan").status_code == 200
    manager.get_wifi_available.assert_awaited_once_with(None)


def test_connect_on_an_interface(client: TestClient, manager: MagicMock) -> None:
    credentials = {"ssid": "home", "password": "secret"}
    response = client.post("/v1.0/connect", params={"interface": "wlan1", "hidden": True}, json=credentials)
    assert response.status_code == 200
    manager.try_connect_to_network.assert_awaited_once_with(WifiCredentials(**credentials), True, "wlan1")


def test_connect_without_interface(client: TestClient, manager: MagicMock) -> None:
    credentials = {"ssid": "home", "password": "secret"}
    assert client.post("/v1.0/connect", json=credentials).status_code == 200
    manager.try_connect_to_network.assert_awaited_once_with(WifiCredentials(**credentials), False, None)


def test_disconnect_an_interface(client: TestClient, manager: MagicMock) -> None:
    assert client.get("/v1.0/disconnect", params={"interface": "wlan1"}).status_code == 200
    manager.disconnect.assert_awaited_once_with("wlan1")


def test_disconnect_without_interface(client: TestClient, manager: MagicMock) -> None:
    assert client.get("/v1.0/disconnect").status_code == 200
    manager.disconnect.assert_awaited_once_with(None)


@pytest.mark.parametrize(
    "method, path, handler",
    [
        ("get", "/v1.0/status", "status"),
        ("get", "/v1.0/scan", "get_wifi_available"),
        ("post", "/v1.0/connect", "try_connect_to_network"),
        ("get", "/v1.0/disconnect", "disconnect"),
        ("post", "/v1.0/hotspot_interface", "set_hotspot_interface"),
    ],
)
def test_unknown_interface_is_not_found(
    client: TestClient, manager: MagicMock, method: str, path: str, handler: str
) -> None:
    kwargs: Any = {"params": {"interface": "wlan9"}}
    if path.endswith("connect"):
        kwargs["json"] = {"ssid": "home", "password": "secret"}
    response = client.request(method, path, **kwargs)
    assert response.status_code == 404
    assert "wlan9" in response.json()["detail"]
    getattr(manager, handler).assert_not_awaited()


@pytest.mark.parametrize(
    "method, path, handler",
    [
        ("get", "/v1.0/status", "status"),
        ("get", "/v1.0/scan", "get_wifi_available"),
        ("post", "/v1.0/connect", "try_connect_to_network"),
        ("get", "/v1.0/disconnect", "disconnect"),
        ("post", "/v1.0/hotspot_interface", "set_hotspot_interface"),
    ],
)
def test_card_unplugged_during_request_is_not_found(
    client: TestClient, manager: MagicMock, method: str, path: str, handler: str
) -> None:
    getattr(manager, handler).side_effect = InterfaceNotFound("wlan1")
    kwargs: Any = {"params": {"interface": "wlan1"}}
    if path.endswith("connect"):
        kwargs["json"] = {"ssid": "home", "password": "secret"}
    response = client.request(method, path, **kwargs)
    assert response.status_code == 404
    assert "wlan1" in response.json()["detail"]


def test_get_hotspot_interface(client: TestClient, manager: MagicMock) -> None:
    response = client.get("/v1.0/hotspot_interface")
    assert response.status_code == 200
    assert response.json() == "wlan1"
    manager.hotspot_interface.assert_awaited_once()


def test_set_hotspot_interface(client: TestClient, manager: MagicMock) -> None:
    assert client.post("/v1.0/hotspot_interface", params={"interface": "wlan1"}).status_code == 200
    manager.set_hotspot_interface.assert_awaited_once_with("wlan1")


def test_set_hotspot_interface_requires_an_interface(client: TestClient, manager: MagicMock) -> None:
    assert client.post("/v1.0/hotspot_interface").status_code == 422
    manager.set_hotspot_interface.assert_not_awaited()
