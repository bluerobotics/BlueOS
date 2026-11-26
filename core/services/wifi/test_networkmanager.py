import asyncio
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

_WIFI_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _WIFI_DIR)
_saved = {name: sys.modules.get(name) for name in ("exceptions", "settings", "typedefs")}
for name in _saved:
    sys.modules.pop(name, None)

from commonwealth.settings.manager import PydanticManager
from sdbus.dbus_exceptions import DbusUnknownMethodError
from sdbus_async.networkmanager import DeviceState, DeviceType
from settings import SettingsV1
from typedefs import WifiCredentials, WifiStatus
from wifi_handlers.networkmanager.networkmanager import NetworkManagerWifi

for name, module in _saved.items():
    if module is not None:
        sys.modules[name] = module
    else:
        sys.modules.pop(name, None)

NM_MODULE = "wifi_handlers.networkmanager.networkmanager"

pytestmark = pytest.mark.asyncio


async def _value(value: Any) -> Any:
    if isinstance(value, Exception):
        raise value
    return value


class _WritableFlag:
    """A dbus property that can be awaited and written, like sdbus's managed."""

    def __init__(self, device: "FakeDevice", property_name: str) -> None:
        self._device = device
        self._property_name = property_name

    def __await__(self) -> Any:
        return self._read().__await__()

    async def _read(self) -> Any:
        value = self._device.properties[self._property_name]
        if isinstance(value, Exception):
            raise value
        return value

    async def set_async(self, value: Any) -> None:
        self._device.properties[self._property_name] = value


class FakeDevice:
    """Mimics a sdbus device proxy, where each property read is awaited."""

    def __init__(
        self,
        interface: str,
        device_type: DeviceType = DeviceType.WIFI,
        state: DeviceState = DeviceState.DISCONNECTED,
        active_connection: str = "/",
    ) -> None:
        self.path = f"/org/freedesktop/NetworkManager/Devices/{interface}"
        self.properties: Dict[str, Any] = {
            "interface": interface,
            "device_type": device_type,
            "state": state,
            "active_connection": active_connection,
            "active_access_point": f"/ap/{interface}",
            "ip4_config": "/",
            "last_scan": 20000,
            "managed": True,
        }
        self.managed = _WritableFlag(self, "managed")
        self.request_scan = AsyncMock()
        self.get_all_access_points = AsyncMock(return_value=[])

    def __getattr__(self, attribute: str) -> Any:
        properties = self.__dict__.get("properties", {})
        if attribute in properties:
            return _value(properties[attribute])
        raise AttributeError(attribute)


class FakeConnectionSettings:
    def __init__(self, paths: List[str]) -> None:
        self.paths = paths
        self.add_connection = AsyncMock(return_value="/conn/new")
        self.delete_connection_by_uuid = AsyncMock()

    @property
    def connections(self) -> Any:
        return _value(self.paths)


def _profile(ssid: str, psk: Optional[str], interface_name: Optional[str]) -> SimpleNamespace:
    return SimpleNamespace(
        wireless=SimpleNamespace(ssid=ssid.encode(), bssid=None),
        wireless_security=SimpleNamespace(psk=psk) if psk else None,
        connection=SimpleNamespace(interface_name=interface_name, uuid=f"uuid-{ssid}"),
    )


# pylint: disable=too-many-instance-attributes
class Harness:
    def __init__(
        self,
        devices: List[FakeDevice],
        profiles: Optional[Dict[str, SimpleNamespace]] = None,
    ) -> None:
        self.devices = devices
        self.profiles = profiles or {}
        self.connections = {
            path: MagicMock(get_profile=AsyncMock(return_value=profile), update_profile=AsyncMock())
            for path, profile in self.profiles.items()
        }
        self.nm = MagicMock()
        self.nm.get_devices = AsyncMock(side_effect=lambda: [device.path for device in self.devices])
        self.nm.activate_connection = AsyncMock()
        self.nm.deactivate_connection = AsyncMock()
        self.nm_settings = FakeConnectionSettings(list(self.profiles))
        self.settings_manager = MagicMock(settings=SettingsV1())
        manager = NetworkManagerWifi.__new__(NetworkManagerWifi)
        manager._bus = MagicMock()
        manager._nm = self.nm
        manager._nm_settings = self.nm_settings  # type: ignore[assignment]
        manager._ap_interface = "uap0"
        manager._unmanaged_interface = None
        manager._tasks = []
        manager._create_ap_process = None
        manager._settings_manager = self.settings_manager
        self.manager = manager

    def device(self, interface: str) -> FakeDevice:
        return next(device for device in self.devices if device.properties["interface"] == interface)

    def _device_proxy(self, path: str, *_args: Any, **_kwargs: Any) -> FakeDevice:
        return next(device for device in self.devices if device.path == path)

    def __enter__(self) -> "Harness":
        self._patches = [
            patch(f"{NM_MODULE}.NetworkDeviceWireless", side_effect=self._device_proxy),
            patch(
                f"{NM_MODULE}.NetworkConnectionSettings",
                side_effect=lambda path, _bus: self.connections[path],
            ),
            patch(
                f"{NM_MODULE}.AccessPoint",
                side_effect=lambda path, _bus: SimpleNamespace(ssid=_value(b"home")),
            ),
        ]
        for patcher in self._patches:
            patcher.start()
        return self

    def __exit__(self, *_args: Any) -> None:
        for patcher in self._patches:
            patcher.stop()


def _two_cards(**kwargs: Any) -> Harness:
    devices = [
        FakeDevice("eth0", device_type=DeviceType.ETHERNET),
        FakeDevice("wlan0"),
        FakeDevice("uap0"),
        FakeDevice("wlan1"),
    ]
    return Harness(devices, **kwargs)


async def test_lists_only_wifi_cards_in_networkmanager_order() -> None:
    with _two_cards() as harness:
        assert await harness.manager.get_interfaces() == ["wlan0", "wlan1"]


async def test_picks_up_hot_plugged_cards() -> None:
    with Harness([FakeDevice("wlan0")]) as harness:
        assert await harness.manager.get_interfaces() == ["wlan0"]
        harness.devices.append(FakeDevice("wlx00c0ca"))
        assert await harness.manager.get_interfaces() == ["wlan0", "wlx00c0ca"]
        harness.devices.pop(0)
        assert await harness.manager.get_interfaces() == ["wlx00c0ca"]


async def test_skips_cards_unplugged_while_listing() -> None:
    with _two_cards() as harness:
        harness.device("wlan0").properties["interface"] = DbusUnknownMethodError("Object does not exist")
        assert await harness.manager.get_interfaces() == ["wlan1"]


async def test_validate_interface() -> None:
    with _two_cards() as harness:
        await harness.manager.validate_interface(None)
        await harness.manager.validate_interface("wlan1")
        with pytest.raises(ValueError, match="'uap0' not found"):
            await harness.manager.validate_interface("uap0")


async def test_status_defaults_to_first_card() -> None:
    with _two_cards() as harness:
        harness.device("wlan1").properties["state"] = DeviceState.ACTIVATED
        status = await harness.manager.status()
        assert (status.interface, status.state) == ("wlan0", "disconnected")


async def test_status_of_a_specific_card() -> None:
    with _two_cards() as harness:
        harness.device("wlan1").properties["state"] = DeviceState.ACTIVATED
        status = await harness.manager.status("wlan1")
        assert status.interface == "wlan1"
        assert status.state == "connected"
        assert status.ssid == "home"


async def test_status_of_unknown_card_raises() -> None:
    with _two_cards() as harness, pytest.raises(ValueError, match="'wlan9' not found"):
        await harness.manager.status("wlan9")


async def test_status_of_card_unplugged_while_reading_raises() -> None:
    with _two_cards() as harness:
        harness.device("wlan1").properties["state"] = DbusUnknownMethodError("Object does not exist")
        with pytest.raises(ValueError, match="'wlan1' not found"):
            await harness.manager.status("wlan1")


async def test_status_without_cards_is_unavailable() -> None:
    with Harness([FakeDevice("eth0", device_type=DeviceType.ETHERNET)]) as harness:
        status = await harness.manager.status()
        assert (status.interface, status.state) == (None, "unavailable")


async def test_scan_uses_the_requested_card() -> None:
    with _two_cards() as harness:
        assert await harness.manager.get_wifi_available("wlan1") == []
        harness.device("wlan1").get_all_access_points.assert_awaited_once()
        harness.device("wlan0").get_all_access_points.assert_not_awaited()


async def test_scan_defaults_to_first_card() -> None:
    with _two_cards() as harness:
        await harness.manager.get_wifi_available()
        harness.device("wlan0").get_all_access_points.assert_awaited_once()
        harness.device("wlan1").get_all_access_points.assert_not_awaited()


async def test_scan_without_cards_is_empty() -> None:
    with Harness([]) as harness:
        assert await harness.manager.get_wifi_available() == []


async def test_scan_of_unknown_card_raises() -> None:
    with _two_cards() as harness, pytest.raises(ValueError, match="'wlan9' not found"):
        await harness.manager.get_wifi_available("wlan9")


def _connected(manager: NetworkManagerWifi) -> AsyncMock:
    status = AsyncMock(return_value=WifiStatus(state="connected"))
    manager.status = status  # type: ignore[method-assign]
    return status


async def test_connect_new_network_on_a_specific_card() -> None:
    with _two_cards() as harness:
        status = _connected(harness.manager)
        await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password="secret"), interface="wlan1")

        profile = harness.nm_settings.add_connection.await_args_list[0].args[0]
        assert profile["connection"]["interface-name"] == ("s", "wlan1")
        assert profile["802-11-wireless-security"]["psk"] == ("s", "secret")
        harness.nm.activate_connection.assert_awaited_once_with("/conn/new", harness.device("wlan1").path, "/")
        status.assert_awaited_with("wlan1")


async def test_connect_defaults_to_first_card() -> None:
    with _two_cards() as harness:
        status = _connected(harness.manager)
        await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password=""))

        profile = harness.nm_settings.add_connection.await_args_list[0].args[0]
        assert profile["connection"]["interface-name"] == ("s", "wlan0")
        assert "802-11-wireless-security" not in profile
        harness.nm.activate_connection.assert_awaited_once_with("/conn/new", harness.device("wlan0").path, "/")
        status.assert_awaited_with("wlan0")


async def test_connect_moves_a_profile_saved_on_another_card() -> None:
    with _two_cards(profiles={"/conn/home": _profile("home", "secret", "wlan0")}) as harness:
        _connected(harness.manager)
        await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password=""), interface="wlan1")

        connection = harness.connections["/conn/home"]
        connection.update_profile.assert_awaited_once_with(harness.profiles["/conn/home"], save_to_disk=True)
        assert harness.profiles["/conn/home"].connection.interface_name == "wlan1"
        harness.nm.activate_connection.assert_awaited_once_with("/conn/home", harness.device("wlan1").path, "/")
        harness.nm_settings.add_connection.assert_not_awaited()


@pytest.mark.parametrize("interface_name", ["wlan1", None])
async def test_connect_keeps_profiles_that_fit_the_card(
    interface_name: Optional[str],
) -> None:
    with _two_cards(profiles={"/conn/home": _profile("home", "secret", interface_name)}) as harness:
        _connected(harness.manager)
        await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password="secret"), interface="wlan1")

        harness.connections["/conn/home"].update_profile.assert_not_awaited()
        harness.nm.activate_connection.assert_awaited_once_with("/conn/home", harness.device("wlan1").path, "/")


async def test_connect_ignores_profiles_with_another_password() -> None:
    with _two_cards(profiles={"/conn/home": _profile("home", "old", "wlan0")}) as harness:
        _connected(harness.manager)
        await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password="new"), interface="wlan1")

        harness.connections["/conn/home"].update_profile.assert_not_awaited()
        harness.nm.activate_connection.assert_awaited_once_with("/conn/new", harness.device("wlan1").path, "/")


async def test_connect_to_unknown_card_raises_before_touching_networkmanager() -> None:
    with _two_cards() as harness:
        with pytest.raises(ValueError, match="'wlan9' not found"):
            await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password=""), interface="wlan9")
        harness.nm.activate_connection.assert_not_awaited()
        harness.nm_settings.add_connection.assert_not_awaited()


async def test_connect_without_cards_raises() -> None:
    with Harness([]) as harness, pytest.raises(RuntimeError, match="No wifi interface"):
        await harness.manager.try_connect_to_network(WifiCredentials(ssid="home", password=""))


async def test_disconnect_only_the_requested_card() -> None:
    with _two_cards() as harness:
        harness.device("wlan0").properties["active_connection"] = "/active/0"
        harness.device("wlan1").properties["active_connection"] = "/active/1"
        await harness.manager.disconnect("wlan1")
        harness.nm.deactivate_connection.assert_awaited_once_with("/active/1")


async def test_disconnect_defaults_to_first_card() -> None:
    with _two_cards() as harness:
        harness.device("wlan0").properties["active_connection"] = "/active/0"
        await harness.manager.disconnect()
        harness.nm.deactivate_connection.assert_awaited_once_with("/active/0")


async def test_disconnect_idle_card_does_nothing() -> None:
    with _two_cards() as harness:
        await harness.manager.disconnect("wlan1")
        harness.nm.deactivate_connection.assert_not_awaited()


async def test_disconnect_without_cards_does_nothing() -> None:
    with Harness([]) as harness:
        await harness.manager.disconnect()
        harness.nm.deactivate_connection.assert_not_awaited()


async def test_disconnect_unknown_card_raises() -> None:
    with _two_cards() as harness, pytest.raises(ValueError, match="'wlan9' not found"):
        await harness.manager.disconnect("wlan9")


async def test_hotspot_interface_defaults_to_first_card() -> None:
    with _two_cards() as harness:
        assert await harness.manager.hotspot_interface() == "wlan0"


async def test_hotspot_interface_uses_the_chosen_card() -> None:
    with _two_cards() as harness:
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        assert await harness.manager.hotspot_interface() == "wlan1"


async def test_hotspot_interface_falls_back_when_chosen_card_is_unplugged() -> None:
    with Harness([FakeDevice("wlan0")]) as harness:
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        assert await harness.manager.hotspot_interface() == "wlan0"


async def test_hotspot_interface_without_cards() -> None:
    with Harness([]) as harness:
        assert await harness.manager.hotspot_interface() is None


def _mock_hotspot(manager: NetworkManagerWifi, running: bool) -> MagicMock:
    hotspot = MagicMock(
        is_running=AsyncMock(return_value=running),
        disable=AsyncMock(),
        enable=AsyncMock(),
    )
    manager.hotspot_is_running = hotspot.is_running  # type: ignore[method-assign]
    manager.disable_hotspot = hotspot.disable  # type: ignore[method-assign]
    manager.enable_hotspot = hotspot.enable  # type: ignore[method-assign]
    return hotspot


async def test_set_hotspot_interface_restarts_running_hotspot_on_new_card() -> None:
    with _two_cards() as harness:
        hotspot = _mock_hotspot(harness.manager, running=True)
        await harness.manager.set_hotspot_interface("wlan1")

        assert harness.manager._settings_manager.settings.hotspot_interface == "wlan1"
        harness.settings_manager.save.assert_called_once()
        assert hotspot.mock_calls == [
            call.is_running(),
            call.disable(save_settings=False),
            call.enable(save_settings=False),
        ]


async def test_set_hotspot_interface_keeps_stopped_hotspot_stopped() -> None:
    with _two_cards() as harness:
        hotspot = _mock_hotspot(harness.manager, running=False)
        await harness.manager.set_hotspot_interface("wlan1")

        assert harness.manager._settings_manager.settings.hotspot_interface == "wlan1"
        # Still removes the AP interface, so it gets recreated on the new card
        hotspot.disable.assert_awaited_once_with(save_settings=False)
        hotspot.enable.assert_not_awaited()


async def test_set_hotspot_interface_rejects_unknown_card() -> None:
    with _two_cards() as harness:
        hotspot = _mock_hotspot(harness.manager, running=True)
        with pytest.raises(ValueError, match="'wlan9' not found"):
            await harness.manager.set_hotspot_interface("wlan9")

        assert harness.manager._settings_manager.settings.hotspot_interface is None
        harness.settings_manager.save.assert_not_called()
        assert not hotspot.mock_calls


def _run(returncode: int = 0) -> MagicMock:
    return MagicMock(returncode=returncode)


def _subprocess_result(command: List[str], *_args: Any, **_kwargs: Any) -> MagicMock:
    result = MagicMock(returncode=0, stdout="")
    if command == ["ip", "link", "show", "uap0"]:
        result.returncode = 1
    elif command[:4] == ["ip", "-j", "link", "show"]:
        result.stdout = json.dumps([{"permaddr": "00:11:22:33:44:55", "address": "02:00:00:00:00:01"}])
    return result


async def test_ap_interface_is_created_on_the_hotspot_card() -> None:
    with _two_cards() as harness, patch(f"{NM_MODULE}.subprocess.run", side_effect=_subprocess_result) as run:
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        assert await harness.manager._create_virtual_interface() is True
        commands = [command.args[0] for command in run.call_args_list]
        assert [
            "iw",
            "dev",
            "wlan1",
            "interface",
            "add",
            "uap0",
            "type",
            "__ap",
        ] in commands
        assert ["ip", "link", "set", "uap0", "address", "02:ff:22:33:44:55"] in commands
        assert ["iw", "wlan1", "set", "power_save", "off"] in commands


async def test_ap_interface_is_not_created_without_cards() -> None:
    with Harness([]) as harness, patch(f"{NM_MODULE}.subprocess.run", return_value=_run(1)) as run:
        assert await harness.manager._create_virtual_interface() is False
        assert len(run.call_args_list) == 1


def _hotspot_process() -> MagicMock:
    process = MagicMock(stdout=io.StringIO("wlan: AP-ENABLED\n"), pid=1)
    process.poll.return_value = None
    return process


async def test_hotspot_unmanages_its_parent_card() -> None:
    with (
        _two_cards() as harness,
        patch(f"{NM_MODULE}.subprocess.Popen", return_value=_hotspot_process()),
        patch.object(harness.manager, "_create_virtual_interface", AsyncMock(return_value=True)),
        patch.object(harness.manager, "_monitor_create_ap_output", AsyncMock()),
    ):
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        assert await harness.manager.enable_hotspot(save_settings=False) is True
        assert harness.device("wlan1").properties["managed"] is False
        assert harness.device("uap0").properties["managed"] is False
        assert harness.device("wlan0").properties["managed"] is True
        with (
            patch(f"{NM_MODULE}.asyncio.sleep", AsyncMock(side_effect=_StopLoop)),
            pytest.raises(_StopLoop),
        ):
            await harness.manager._autoscan()
        harness.device("wlan0").request_scan.assert_awaited_once_with({})
        harness.device("wlan1").request_scan.assert_not_awaited()


async def test_failed_hotspot_manages_its_parent_card_again() -> None:
    with (
        _two_cards() as harness,
        patch.object(harness.manager, "_create_virtual_interface", AsyncMock(return_value=False)),
    ):
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        assert await harness.manager.enable_hotspot(save_settings=False) is False
        assert harness.device("wlan1").properties["managed"] is True
        assert harness.manager._unmanaged_interface is None


async def test_disabling_hotspot_manages_the_card_that_was_unmanaged() -> None:
    with (
        _two_cards() as harness,
        patch(f"{NM_MODULE}.subprocess.Popen", return_value=_hotspot_process()),
        patch.object(harness.manager, "_create_virtual_interface", AsyncMock(return_value=True)),
        patch.object(harness.manager, "_monitor_create_ap_output", AsyncMock()),
        patch(f"{NM_MODULE}.subprocess.run", side_effect=_subprocess_result),
    ):
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        assert await harness.manager.enable_hotspot(save_settings=False) is True
        harness.manager._settings_manager.settings.hotspot_interface = "wlan0"
        await harness.manager.disable_hotspot(save_settings=False)
        assert harness.device("wlan1").properties["managed"] is True
        assert harness.device("wlan0").properties["managed"] is True
        assert harness.manager._unmanaged_interface is None


async def test_start_manages_cards_left_unmanaged() -> None:
    with (
        _two_cards() as harness,
        patch.object(harness.manager, "_create_virtual_interface", AsyncMock(return_value=True)),
        patch.object(asyncio.get_running_loop(), "add_signal_handler"),
    ):
        harness.device("wlan0").properties["managed"] = False
        harness.device("wlan1").properties["managed"] = False
        await harness.manager.start()
        assert harness.device("wlan0").properties["managed"] is True
        assert harness.device("wlan1").properties["managed"] is True
        assert harness.device("uap0").properties["managed"] is True
        for task in harness.manager._tasks:
            task.cancel()
        await asyncio.gather(*harness.manager._tasks, return_exceptions=True)


async def test_watchdog_keeps_the_hotspot_card_unmanaged() -> None:
    sleeps = 0

    async def _sleep(_seconds: float) -> None:
        nonlocal sleeps
        sleeps += 1
        if sleeps > 1:
            raise _StopLoop

    with _two_cards() as harness, patch(f"{NM_MODULE}.asyncio.sleep", side_effect=_sleep):
        harness.manager._settings_manager.settings.hotspot_enabled = False
        harness.manager._settings_manager.settings.smart_hotspot_enabled = False
        harness.manager._settings_manager.settings.hotspot_interface = "wlan1"
        harness.manager._create_ap_process = MagicMock()
        harness.manager._create_ap_process.poll.return_value = None
        with pytest.raises(_StopLoop):
            await harness.manager.hotspot_watchdog()
        assert harness.device("wlan1").properties["managed"] is False
        assert harness.device("uap0").properties["managed"] is False


async def test_create_ap_exit_manages_the_hotspot_card() -> None:
    process = MagicMock()
    process.stdout = io.StringIO("")
    process.poll.side_effect = [None, 0]
    with (
        _two_cards() as harness,
        patch(f"{NM_MODULE}.select.select", return_value=([], [], [])),
        patch(f"{NM_MODULE}.asyncio.sleep", AsyncMock()),
    ):
        harness.manager._unmanaged_interface = "wlan1"
        harness.device("wlan1").properties["managed"] = False
        harness.manager._create_ap_process = process
        await harness.manager._monitor_create_ap_output(process)
        assert harness.device("wlan1").properties["managed"] is True
        assert harness.manager._unmanaged_interface is None


async def test_hotspot_runs_directly_on_the_ap_interface() -> None:
    process = MagicMock(stdout=io.StringIO("wlan: AP-ENABLED\n"), pid=1)
    process.poll.return_value = None
    with (
        _two_cards() as harness,
        patch(f"{NM_MODULE}.subprocess.Popen", return_value=process) as popen,
        patch.object(harness.manager, "_create_virtual_interface", AsyncMock(return_value=True)),
        patch.object(harness.manager, "_monitor_create_ap_output", AsyncMock()),
    ):
        assert await harness.manager.enable_hotspot(save_settings=False) is True
        command = popen.call_args.args[0]
        assert command[:3] == ["create_ap", "-n", "uap0"]
        assert "--no-virt" in command


class _StopLoop(Exception):
    pass


async def test_autoscan_scans_every_card_even_if_one_fails() -> None:
    with _two_cards() as harness, patch(f"{NM_MODULE}.asyncio.sleep", AsyncMock(side_effect=_StopLoop)):
        harness.device("wlan0").request_scan.side_effect = RuntimeError("busy")
        with pytest.raises(_StopLoop):
            await harness.manager._autoscan()
        harness.device("wlan0").request_scan.assert_awaited_once_with({})
        harness.device("wlan1").request_scan.assert_awaited_once_with({})
        harness.device("uap0").request_scan.assert_not_awaited()


async def test_any_interface_connected() -> None:
    with _two_cards() as harness:
        assert await harness.manager._is_any_interface_connected() is False
        harness.device("wlan1").properties["state"] = DeviceState.ACTIVATED
        assert await harness.manager._is_any_interface_connected() is True


async def test_any_interface_connected_tolerates_unplugged_cards() -> None:
    with _two_cards() as harness:
        status = AsyncMock(side_effect=[RuntimeError("gone"), WifiStatus(state="connected")])
        harness.manager.status = status  # type: ignore[method-assign]
        assert await harness.manager._is_any_interface_connected() is True
        assert status.await_args_list == [call("wlan0"), call("wlan1")]


async def test_settings_migrate_from_v1(tmp_path: Path) -> None:
    folder = tmp_path / "wifi-manager"
    folder.mkdir()
    v1 = {
        "VERSION": 1,
        "hotspot_enabled": True,
        "hotspot_ssid": "boat",
        "smart_hotspot_enabled": False,
    }
    (folder / "settings-1.json").write_text(json.dumps(v1), encoding="utf-8")

    settings = PydanticManager("wifi-manager", SettingsV1, tmp_path).settings

    assert settings.VERSION == 1
    assert settings.hotspot_enabled is True
    assert settings.hotspot_ssid == "boat"
    assert settings.smart_hotspot_enabled is False
    assert settings.hotspot_interface is None
