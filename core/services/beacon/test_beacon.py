import asyncio
import enum
import json
import os
import socket
import sys
import tempfile
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

BEACON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BEACON_DIR))
# commonwealth is not installed in the 1.4 test env, but its settings manager only needs pykson and appdirs,
# so the real one is loaded by path to keep the settings persistence and migration tests meaningful
sys.path.append(str(BEACON_DIR.parent.parent / "libs" / "commonwealth"))


class IPVersion(enum.Enum):
    V4Only = 1
    V6Only = 2
    All = 3


class AsyncServiceInfo:
    def __init__(self, type_: str, name: str, **kwargs: Any) -> None:
        self.type = type_
        self.name = name
        self.kwargs = kwargs

    def __repr__(self) -> str:
        return f"AsyncServiceInfo({self.type!r}, {self.name!r}, {sorted(self.kwargs.items())!r})"


class FakeApp:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def _route(self, *_args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda function: function

    get = post = mount = _route


class Request:
    def __init__(self, scope: Dict[str, Any]) -> None:
        self.scope = scope
        self.headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}


def module(name: str, **attributes: Any) -> types.ModuleType:
    stub = types.ModuleType(name)
    stub.__dict__.update(attributes)
    return stub


# The 1.4 test env has no fastapi, starlette, uvicorn or zeroconf, so main.py imports are replaced by stand-ins
_STUBS = {
    "commonwealth.utils.apis": module("commonwealth.utils.apis", PrettyJSONResponse=MagicMock()),
    "commonwealth.utils.logs": module("commonwealth.utils.logs", init_logger=MagicMock()),
    "fastapi": module("fastapi", FastAPI=FakeApp, Request=Request),
    "fastapi.responses": module("fastapi.responses", HTMLResponse=MagicMock()),
    "fastapi_versioning": module(
        "fastapi_versioning",
        VersionedFastAPI=lambda app, **_kwargs: app,
        version=lambda *_args, **_kwargs: lambda function: function,
    ),
    "uvicorn": module("uvicorn", Config=MagicMock(), Server=MagicMock()),
    "zeroconf": module("zeroconf", IPVersion=IPVersion),
    "zeroconf.asyncio": module("zeroconf.asyncio", AsyncServiceInfo=AsyncServiceInfo, AsyncZeroconf=MagicMock()),
}
_saved = {name: sys.modules.pop(name, None) for name in ("main", "settings", "typedefs", *_STUBS)}
sys.modules.update(_STUBS)

# main.py creates a Beacon at import time, which would write to the real settings folder
with patch.dict(os.environ, {"XDG_CONFIG_HOME": tempfile.mkdtemp(prefix="beacon-test-")}):
    import main as beacon
    from settings import Interface, InvalidIpAddress
    from typedefs import InterfaceType, IpInfo

# Restore after import so other collected tests still see the real modules (pytest-xdist)
for module_name, saved_module in _saved.items():
    if saved_module is not None:
        sys.modules[module_name] = saved_module
    else:
        sys.modules.pop(module_name, None)


def ipv4(address: str) -> SimpleNamespace:
    return SimpleNamespace(family=socket.AF_INET, address=address)


ADDRESSES = {
    "eth0": [ipv4("192.168.2.2"), SimpleNamespace(family=socket.AF_INET6, address="fe80::1"), ipv4("10.0.0.2")],
    "wlan0": [ipv4("192.168.1.5")],
    "usb0": [ipv4("192.168.3.1")],
    "lo": [ipv4("127.0.0.1")],
    "docker0": [ipv4("172.17.0.1")],
}
STATS = {
    "eth0": SimpleNamespace(isup=True),
    "wlan0": SimpleNamespace(isup=True),
    "usb0": SimpleNamespace(isup=False),
    "lo": SimpleNamespace(isup=True),
    "docker0": SimpleNamespace(isup=True),
}
V1_SETTINGS = {
    "VERSION": 1,
    "default": {"domain_names": ["blueos", "myboat"], "advertise": ["_http"], "ip": "ips[0]"},
    "blacklist": ["lo"],
    "interfaces": [
        {
            "name": "wlan0",
            "domain_names": ["blueos", "companion", "myboat-wifi"],
            "advertise": ["_http"],
            "ip": "ips[0]",
        }
    ],
    "advertisement_types": [{"name": "_http", "protocol": "_tcp", "port": 80}],
}


@pytest.fixture(name="settings_dir")
def fixture_settings_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(psutil, "net_if_addrs", lambda: ADDRESSES)
    monkeypatch.setattr(psutil, "net_if_stats", lambda: STATS)
    return tmp_path / "beacon"


def test_first_boot_loads_defaults(settings_dir: Path) -> None:
    manager = beacon.Beacon()
    assert set(manager.service_types) == {"_mavlink", "_http"}
    assert manager.service_types["_mavlink"].get_properties() == {"name": "ardusub"}
    assert manager.get_hostname() == "blueos"
    assert manager.settings.default.domain_names == ["blueos"]
    assert manager.get_vehicle_name() == "BlueROV2"
    assert (settings_dir / "settings-4.json").exists()


def test_migrates_v1_settings_to_v4(settings_dir: Path) -> None:
    settings_dir.mkdir()
    (settings_dir / "settings-1.json").write_text(json.dumps(V1_SETTINGS), encoding="utf-8")
    settings = beacon.Beacon().settings
    assert settings.VERSION == 4
    assert settings.default.domain_names == ["myboat"]
    assert {interface.name: interface.domain_names for interface in settings.interfaces} == {
        "wlan0": ["myboat-wifi"],
        "uap0": ["blueos-hotspot"],
    }


@pytest.mark.parametrize("content", ["{not json", "", json.dumps({"VERSION": 4, "default": "oops"})])
def test_broken_settings_file_falls_back_to_defaults(settings_dir: Path, content: str) -> None:
    settings_dir.mkdir()
    (settings_dir / "settings-4.json").write_text(content, encoding="utf-8")
    manager = beacon.Beacon()
    assert set(manager.service_types) == {"_mavlink", "_http"}
    assert manager.get_hostname() == "blueos"
    assert {interface.name: interface.domain_names for interface in manager.settings.interfaces} == {
        "eth0": ["blueos", "blueos-ethernet", "companion"],
        "wlan0": ["blueos-wifi"],
        "uap0": ["blueos-hotspot"],
    }
    json.loads((settings_dir / "settings-4.json").read_text(encoding="utf-8"))


@pytest.mark.usefixtures("settings_dir")
def test_hostname_and_vehicle_name_persist_per_interface_type() -> None:
    manager = beacon.Beacon()
    manager.set_hostname("myrov")
    manager.set_vehicle_name("Nautilus")
    restarted = beacon.Beacon()
    assert {interface.name: interface.domain_names for interface in restarted.settings.interfaces} == {
        "eth0": ["myrov", "myrov-ethernet", "companion", "blueos"],
        "wlan0": ["myrov-wifi"],
        "uap0": ["myrov-hotspot"],
    }
    assert restarted.get_hostname() == "myrov"
    assert restarted.get_vehicle_name() == "Nautilus"


@pytest.mark.usefixtures("settings_dir")
def test_renaming_replaces_the_previous_hostname_on_wired_interfaces() -> None:
    manager = beacon.Beacon()
    for hostname in ["myrov", "myrov", "blueos2", "blueos2"]:
        manager.set_hostname(hostname)
    eth0 = manager.settings.get_interface_or_create_default("eth0")
    assert eth0.domain_names == ["blueos2", "blueos2-ethernet", "companion", "blueos"]
    manager.set_hostname("blueos")
    assert eth0.domain_names == ["blueos", "blueos-ethernet", "companion"]


@pytest.mark.usefixtures("settings_dir")
@pytest.mark.parametrize(
    "ip, expected",
    [
        ("ips[*]", ["192.168.2.2", "10.0.0.2"]),
        ("ips[1]", ["10.0.0.2"]),
        ("ips[9]", []),
        ("192.168.2.10", ["192.168.2.10"]),
    ],
)
def test_interface_ip_selection(ip: str, expected: List[str]) -> None:
    assert Interface(name="eth0", ip=ip).get_ip_strs() == expected


def test_interface_rejects_non_ipv4() -> None:
    with pytest.raises(InvalidIpAddress):
        Interface(name="eth0", ip="fe80::1").get_ip_strs()


@pytest.mark.parametrize(
    "name, interface_type",
    [
        ("wlan0", InterfaceType.WIFI),
        ("uap0", InterfaceType.HOTSPOT),
        ("eth0", InterfaceType.WIRED),
        ("enp3s0", InterfaceType.WIRED),
        ("usb0", InterfaceType.USB),
        ("tun0", InterfaceType.UNKNOWN),
    ],
)
def test_guess_interface_type(name: str, interface_type: InterfaceType) -> None:
    assert InterfaceType.guess_from_name(name) == interface_type


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_dir")
async def test_run_advertises_up_interfaces_and_replaces_changed_runners(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = beacon.Beacon()
    manager.set_hostname("myrov")
    register, unregister = AsyncMock(), AsyncMock()
    monkeypatch.setattr(beacon.AsyncRunner, "register_services", register)
    monkeypatch.setattr(beacon.AsyncRunner, "unregister_services", unregister)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    monkeypatch.setattr(beacon, "beacon", manager)

    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    entries = beacon.get_services()
    assert {(entry.hostname, entry.service_type, entry.ip, entry.interface_type) for entry in entries} >= {
        ("myrov-eth0-1", "_http", "192.168.2.2", InterfaceType.WIRED),
        ("companion", "_mavlink", "10.0.0.2", InterfaceType.WIRED),
        ("myrov-wifi", "_http", "192.168.1.5", InterfaceType.WIFI),
    }
    assert {entry.interface for entry in entries} == {"eth0", "wlan0"}
    assert register.await_count == len(manager.runners)
    unregister.assert_not_awaited()

    manager.manager.settings.get_interface_or_create_default("wlan0").advertise.append("_mavlink")
    manager.manager.save()
    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    unregister.assert_awaited_once()
    assert register.await_count == len(manager.runners) + 1
    wifi_services = {entry.service_type for entry in beacon.get_services() if entry.hostname == "myrov-wifi"}
    assert wifi_services == {"_http", "_mavlink"}


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_dir")
async def test_run_advertises_interfaces_without_settings_using_the_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(STATS, "usb0", SimpleNamespace(isup=True))
    manager = beacon.Beacon()
    manager.set_hostname("myrov")
    monkeypatch.setattr(beacon.AsyncRunner, "register_services", AsyncMock())
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    monkeypatch.setattr(beacon, "beacon", manager)

    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    usb_entries = {
        (entry.hostname, entry.ip, entry.interface_type) for entry in beacon.get_services() if entry.interface == "usb0"
    }
    assert usb_entries == {
        ("myrov", "192.168.3.1", InterfaceType.USB),
        ("myrov-usb0-1", "192.168.3.1", InterfaceType.USB),
    }


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_dir")
async def test_run_unregisters_runners_that_are_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = beacon.Beacon()
    unregister = AsyncMock()
    monkeypatch.setattr(beacon.AsyncRunner, "register_services", AsyncMock())
    monkeypatch.setattr(beacon.AsyncRunner, "unregister_services", unregister)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))
    monkeypatch.setattr(beacon, "beacon", manager)

    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    wifi_runners = sum(runner.interface_name == "wlan0" for runner in manager.runners.values())
    monkeypatch.setitem(STATS, "wlan0", SimpleNamespace(isup=False))
    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    assert {entry.interface for entry in beacon.get_services()} == {"eth0"}
    assert wifi_runners > 0
    assert unregister.await_count == wifi_runners


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["register_services", "unregister_services"])
async def test_runner_closes_zeroconf_when_it_fails(method: str, monkeypatch: pytest.MonkeyPatch) -> None:
    aiozc = MagicMock(
        async_register_service=AsyncMock(side_effect=OSError("interface gone")),
        async_unregister_service=AsyncMock(side_effect=OSError("interface gone")),
        async_close=AsyncMock(),
    )
    monkeypatch.setattr(beacon, "AsyncZeroconf", MagicMock(return_value=aiozc))
    runner = beacon.AsyncRunner(IPVersion.V4Only, interface="192.168.2.2", interface_name="eth0")
    runner.add_services(MagicMock())
    runner.aiozc = aiozc

    with pytest.raises(OSError):
        await getattr(runner, method)()
    aiozc.async_close.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.usefixtures("settings_dir")
async def test_run_keeps_going_when_updating_a_changed_runner_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = beacon.Beacon()
    register = AsyncMock()
    monkeypatch.setattr(beacon.AsyncRunner, "register_services", register)
    monkeypatch.setattr(beacon.AsyncRunner, "unregister_services", AsyncMock(side_effect=OSError("interface gone")))
    monkeypatch.setattr(asyncio, "sleep", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    total = len(manager.runners)
    manager.manager.settings.get_interface_or_create_default("wlan0").advertise.append("_mavlink")
    manager.manager.save()

    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    failed = total - len(manager.runners)
    assert failed > 0

    register.reset_mock()
    with pytest.raises(asyncio.CancelledError):
        await manager.run()
    assert len(manager.runners) == total
    assert register.await_count == failed


def test_get_ip_prefers_nginx_headers() -> None:
    scope = {"type": "http", "client": ("192.168.2.10", 5000), "server": ("192.168.2.2", 9111)}
    assert beacon.get_ip(Request({**scope, "headers": []})) == IpInfo(
        client_ip="192.168.2.10", interface_ip="192.168.2.2"
    )
    headers = [(b"x-real-ip", b"10.0.0.5"), (b"x-interface-ip", b"10.0.0.2")]
    assert beacon.get_ip(Request({**scope, "headers": headers})) == IpInfo(
        client_ip="10.0.0.5", interface_ip="10.0.0.2"
    )
