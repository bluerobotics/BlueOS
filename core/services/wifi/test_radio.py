import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import radio

pytestmark = pytest.mark.asyncio


def _add_device(root: Path, name: str, kind: str, soft: str, hard: str) -> Path:
    device = root / name
    device.mkdir()
    for attribute, value in {"type": kind, "soft": soft, "hard": hard}.items():
        (device / attribute).write_text(f"{value}\n")
    return device


async def test_rfkill_status_only_reads_wifi_devices(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _add_device(tmp_path, "rfkill0", "bluetooth", "0", "1")
    _add_device(tmp_path, "rfkill1", "wlan", "1", "0")
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)

    status = await radio.rfkill_status()

    assert status.soft_blocked is True
    assert status.hard_blocked is False


async def test_rfkill_status_skips_a_device_that_vanishes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _add_device(tmp_path, "rfkill0", "wlan", "1", "0")
    (tmp_path / "rfkill1").mkdir()
    gone = _add_device(tmp_path, "rfkill2", "wlan", "0", "0")
    (gone / "soft").unlink()
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)

    status = await radio.rfkill_status()

    assert status.soft_blocked is True
    assert status.hard_blocked is False


async def test_rfkill_status_without_radio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path / "missing")

    status = await radio.rfkill_status()

    assert (status.soft_blocked, status.hard_blocked) == (False, False)


async def test_rfkill_unblock_clears_only_the_wifi_soft_block(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bluetooth = _add_device(tmp_path, "rfkill0", "bluetooth", "1", "0")
    wifi = _add_device(tmp_path, "rfkill1", "wlan", "1", "0")
    monkeypatch.setattr(radio, "RFKILL_PATH", tmp_path)

    await radio.rfkill_unblock()

    assert (wifi / "soft").read_text() == "0"
    assert (bluetooth / "soft").read_text().strip() == "1"
