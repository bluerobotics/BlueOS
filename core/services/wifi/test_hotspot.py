import sys
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any, List
from unittest.mock import AsyncMock, MagicMock, patch

_WIFI_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _WIFI_DIR)
for _name in ("exceptions", "settings", "typedefs"):
    _mod = sys.modules.get(_name)
    if _mod is not None and not str(getattr(_mod, "__file__", "")).startswith(_WIFI_DIR):
        del sys.modules[_name]

sys.modules["pyroute2"] = MagicMock()
sys.modules["settings"] = MagicMock()
# Restore after import so other collected tests still see real commonwealth (pytest-xdist).
_STUBBED = (
    "commonwealth",
    "commonwealth.utils",
    "commonwealth.utils.DHCPServerManager",
    "commonwealth.utils.general",
    "commonwealth.settings",
    "commonwealth.settings.manager",
    "commonwealth.settings.settings",
    "fastapi",
)
_previous = {name: sys.modules.get(name) for name in _STUBBED}
for name in _STUBBED:
    sys.modules[name] = MagicMock()

import pytest

from wifi_handlers.wpa_supplicant.Hotspot import HotspotManager
from wifi_handlers.wpa_supplicant.WifiManager import WifiManager

for name, previous in _previous.items():
    if previous is None:
        del sys.modules[name]
    else:
        sys.modules[name] = previous


def _bare_hotspot() -> HotspotManager:
    hotspot = HotspotManager.__new__(HotspotManager)
    hotspot.supports_hotspot = True
    hotspot._ap_interface_name = "uap0"
    hotspot._subprocess = None
    hotspot._dhcp_server = None
    hotspot._ipv4_gateway = IPv4Address("192.168.42.1")
    return hotspot


def _alive_process() -> MagicMock:
    process = MagicMock()
    process.poll.return_value = None
    process.returncode = None
    return process


def test_is_running_is_false_when_uap0_is_down() -> None:
    hotspot = _bare_hotspot()
    hotspot._subprocess = _alive_process()
    down = MagicMock(isup=False)
    with patch("wifi_handlers.wpa_supplicant.Hotspot.psutil.net_if_stats", return_value={"uap0": down}):
        assert hotspot.is_running() is False


def test_is_running_is_true_when_hostapd_alive_and_uap0_up() -> None:
    hotspot = _bare_hotspot()
    hotspot._subprocess = _alive_process()
    up = MagicMock(isup=True)
    with patch("wifi_handlers.wpa_supplicant.Hotspot.psutil.net_if_stats", return_value={"uap0": up}):
        assert hotspot.is_running() is True


def test_stop_kills_hostapd_even_if_uap0_is_down() -> None:
    hotspot = _bare_hotspot()
    process = _alive_process()
    hotspot._subprocess = process
    hotspot._dhcp_server = MagicMock()
    with patch("wifi_handlers.wpa_supplicant.Hotspot.psutil.net_if_stats", return_value={}):
        hotspot.stop()
    process.kill.assert_called_once()
    hotspot._dhcp_server.stop.assert_called_once()


@pytest.mark.asyncio
async def test_start_kills_leftover_hostapd_before_recreating_uap0() -> None:
    hotspot = _bare_hotspot()
    leftover = _alive_process()
    hotspot._subprocess = leftover
    events: List[str] = []
    leftover.kill.side_effect = lambda: events.append("kill")

    def create_interface() -> None:
        events.append("create")

    new_process = _alive_process()

    def popen(*_args: Any, **_kwargs: Any) -> MagicMock:
        events.append("popen")
        return new_process

    with (
        patch.object(hotspot, "_create_temp_config_file"),
        patch.object(hotspot, "_create_virtual_interface", side_effect=create_interface),
        patch.object(hotspot, "command_list", return_value=["hostapd", "conf"]),
        patch("wifi_handlers.wpa_supplicant.Hotspot.subprocess.Popen", side_effect=popen),
        patch("wifi_handlers.wpa_supplicant.Hotspot.asyncio.sleep", new_callable=AsyncMock),
        patch("wifi_handlers.wpa_supplicant.Hotspot.DHCPServerManager"),
    ):
        await hotspot.start()

    assert events == ["kill", "create", "popen"]


@pytest.mark.asyncio
async def test_enable_hotspot_skips_start_when_already_running() -> None:
    manager = WifiManager.__new__(WifiManager)
    hotspot = MagicMock()
    hotspot.is_running.return_value = True
    hotspot.start = AsyncMock()
    manager._hotspot = hotspot
    assert await manager.enable_hotspot(save_settings=False) is True
    hotspot.start.assert_not_called()
