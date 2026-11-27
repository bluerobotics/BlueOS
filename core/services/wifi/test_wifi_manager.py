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

import radio
from wifi_handlers import AbstractWifiHandler as wifi_abstract
from wifi_handlers.AbstractWifiHandler import AbstractWifiManager
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


class _CountrySocket:
    def __init__(self, failing: str) -> None:
        self.sent: list[str] = []
        self.failing = failing

    def send(self, data: bytes) -> None:
        self.sent.append(data.decode())

    def recvfrom(self, _size: int) -> tuple[bytes, None]:
        return (b"FAIL\n" if self.sent[-1] == self.failing else b"OK\n"), None


@pytest.mark.parametrize("previous", ["BR", "00"])
async def test_failing_to_save_the_country_restores_the_previous_one(
    monkeypatch: pytest.MonkeyPatch, previous: str
) -> None:
    manager = WifiManager.__new__(WifiManager)
    manager.wpa_path = "wlan0"
    wpa_socket = _CountrySocket("SAVE_CONFIG")
    kernel: list[str] = []

    async def current_country() -> str:
        return previous

    async def set_country(code: str) -> None:
        kernel.append(code)

    monkeypatch.setattr(manager.wpa, "sock", wpa_socket)
    monkeypatch.setattr(radio, "current_country", current_country)
    monkeypatch.setattr(radio, "set_country", set_country)

    with pytest.raises(Exception, match="SAVE_CONFIG failed"):
        await manager.set_country("US")

    assert wpa_socket.sent == ["SET country US", "SAVE_CONFIG", f"SET country {previous}"]
    assert kernel == [previous]


@pytest.mark.parametrize("previous", ["BR", "00"])
@pytest.mark.parametrize("restore_fails", [False, True])
async def test_failing_to_apply_the_saved_country_persists_the_previous_one(
    monkeypatch: pytest.MonkeyPatch, previous: str, restore_fails: bool
) -> None:
    manager = WifiManager.__new__(WifiManager)
    manager.wpa_path = "wlan0"
    wpa_socket = _CountrySocket("")
    kernel: list[str] = []

    async def current_country() -> str:
        return previous

    async def set_country(code: str) -> None:
        kernel.append(code)
        if code == "US" or restore_fails:
            raise RuntimeError("kernel refused")

    monkeypatch.setattr(manager.wpa, "sock", wpa_socket)
    monkeypatch.setattr(radio, "current_country", current_country)
    monkeypatch.setattr(radio, "set_country", set_country)
    monkeypatch.setattr(radio, "rfkill_unblock", AsyncMock())

    with pytest.raises(RuntimeError, match="kernel refused"):
        await manager.set_country("US")

    assert wpa_socket.sent == ["SET country US", "SAVE_CONFIG", f"SET country {previous}", "SAVE_CONFIG"]
    assert kernel == ["US", previous]


async def test_failing_to_set_the_country_does_not_save_the_previous_one(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WifiManager.__new__(WifiManager)
    manager.wpa_path = "wlan0"
    wpa_socket = _CountrySocket("SET country US")
    monkeypatch.setattr(manager.wpa, "sock", wpa_socket)
    monkeypatch.setattr(radio, "current_country", AsyncMock(return_value="BR"))
    monkeypatch.setattr(radio, "set_country", AsyncMock())

    with pytest.raises(Exception, match="SET country US failed"):
        await manager.set_country("US")

    assert wpa_socket.sent == ["SET country US", "SET country BR"]


async def test_failing_to_restore_the_country_raises_the_original_error(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WifiManager.__new__(WifiManager)
    manager.wpa_path = "wlan0"
    wpa_socket = _CountrySocket("SET country BR")
    monkeypatch.setattr(manager.wpa, "sock", wpa_socket)
    monkeypatch.setattr(radio, "current_country", AsyncMock(return_value="BR"))
    monkeypatch.setattr(radio, "set_country", AsyncMock(side_effect=RuntimeError("kernel refused")))
    monkeypatch.setattr(radio, "rfkill_unblock", AsyncMock())

    with pytest.raises(RuntimeError, match="kernel refused"):
        await manager.set_country("US")

    assert wpa_socket.sent == ["SET country US", "SAVE_CONFIG", "SET country BR"]


@pytest.fixture(name="fresh_country_lock")
def fixture_fresh_country_lock() -> Any:
    wifi_abstract._country_lock.cache_clear()
    yield
    wifi_abstract._country_lock.cache_clear()


@pytest.mark.usefixtures("fresh_country_lock")
async def test_overlapping_country_changes_run_one_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = AbstractWifiManager.__new__(AbstractWifiManager)  # type: ignore[type-abstract]
    events: list[str] = []

    async def apply_country(code: str) -> None:
        events.append(f"start {code}")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        events.append(f"end {code}")

    monkeypatch.setattr(manager, "_apply_country", apply_country)

    await asyncio.gather(manager.set_country("US"), manager.set_country("BR"))

    assert events == ["start US", "end US", "start BR", "end BR"]


def _manager(monkeypatch: pytest.MonkeyPatch, saved: str | None, current: str, *, real_set: bool = False) -> Any:
    manager = AbstractWifiManager.__new__(AbstractWifiManager)  # type: ignore[type-abstract]
    manager._settings_manager = SimpleNamespace(  # type: ignore[assignment]
        settings=SimpleNamespace(regulatory_country=saved), save=lambda: None
    )
    monkeypatch.setattr(radio, "current_country", AsyncMock(return_value=current))
    if not real_set:
        monkeypatch.setattr(radio, "set_country", AsyncMock())
    monkeypatch.setattr(radio, "rfkill_unblock", AsyncMock())
    return manager


async def test_applying_without_a_saved_country_leaves_the_system_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(monkeypatch, None, "00")

    await manager.apply_saved_country()

    radio.set_country.assert_not_awaited()  # type: ignore[attr-defined]


async def test_applying_the_country_already_active_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(monkeypatch, "BR", "BR")

    await manager.apply_saved_country()

    radio.set_country.assert_not_awaited()  # type: ignore[attr-defined]


async def test_applying_a_different_saved_country_sets_it(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(monkeypatch, "BR", "00")

    await manager.apply_saved_country()

    radio.set_country.assert_awaited_once_with("BR")  # type: ignore[attr-defined]


async def test_applying_an_invalid_saved_country_raises_for_main_to_log(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(monkeypatch, "br;", "00", real_set=True)

    with pytest.raises(ValueError):
        await manager.apply_saved_country()


async def test_setting_a_country_unblocks_the_radio_and_saves_it(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = _manager(monkeypatch, None, "00")
    monkeypatch.setattr(manager, "rfkill_unblock", AsyncMock())

    await manager.set_country("US")

    manager.rfkill_unblock.assert_awaited_once()
    assert manager._settings_manager.settings.regulatory_country == "US"


async def test_an_invalid_country_never_reaches_the_wpa_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = WifiManager.__new__(WifiManager)
    manager.wpa_path = "wlan0"
    wpa_socket = _CountrySocket("")
    monkeypatch.setattr(manager.wpa, "sock", wpa_socket)

    with pytest.raises(ValueError):
        await manager.set_country("US\nSET update_config 0")

    assert not wpa_socket.sent


async def _no_networks(_self: Any) -> list[Any]:
    return []
