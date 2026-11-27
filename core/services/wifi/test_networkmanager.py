import sys
from pathlib import Path
from typing import Any

import pytest

_WIFI_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _WIFI_DIR)
_saved = {name: sys.modules.get(name) for name in ("exceptions", "settings", "typedefs")}
for name in _saved:
    sys.modules.pop(name, None)

import radio
from wifi_handlers.networkmanager.networkmanager import NetworkManagerWifi

for name, module in _saved.items():
    if module is not None:
        sys.modules[name] = module
    else:
        sys.modules.pop(name, None)

pytestmark = pytest.mark.asyncio


class _Property:
    def __init__(self, value: bool, applies_after: int = 0) -> None:
        self.value = value
        self.pending: bool | None = None
        self.reads_left = applies_after

    def __await__(self) -> Any:
        async def read() -> bool:
            if self.pending is not None:
                if self.reads_left <= 0:
                    self.value, self.pending = self.pending, None
                self.reads_left -= 1
            return self.value

        return read().__await__()

    async def set_async(self, value: bool) -> None:
        self.pending = value


def _manager(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, enabled: _Property, hardware: bool) -> Any:
    manager = NetworkManagerWifi.__new__(NetworkManagerWifi)
    manager._nm = type("FakeNM", (), {"wireless_enabled": enabled, "wireless_hardware_enabled": _Property(hardware)})()  # type: ignore
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)
    return manager


async def test_networkmanager_switch_off_counts_as_a_soft_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manager = _manager(monkeypatch, tmp_path, _Property(False), hardware=True)

    status = await manager.rfkill_status()

    assert (status.soft_blocked, status.hard_blocked) == (True, False)


async def test_networkmanager_hardware_switch_counts_as_a_hard_block(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    manager = _manager(monkeypatch, tmp_path, _Property(True), hardware=False)

    status = await manager.rfkill_status()

    assert (status.soft_blocked, status.hard_blocked) == (False, True)


async def test_unblocking_waits_for_networkmanager_to_report_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    enabled = _Property(False, applies_after=3)
    manager = _manager(monkeypatch, tmp_path, enabled, hardware=True)
    sleeps = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("wifi_handlers.networkmanager.networkmanager.asyncio.sleep", fake_sleep)

    await manager.rfkill_unblock()

    assert enabled.value is True
    assert len(sleeps) == 3
