import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from portwatcher import PortWatcher


@pytest.mark.asyncio
async def test_start_watching_continues_after_add_ping360_error() -> None:
    watcher = PortWatcher(probe_callback=AsyncMock(), found_callback=AsyncMock())
    calls = 0

    async def flaky_add_ping360() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise KeyError("uap0")
        raise asyncio.CancelledError()

    with (
        patch.object(watcher, "add_ping360", side_effect=flaky_add_ping360),
        patch("portwatcher.serial.tools.list_ports.comports", return_value=[]),
        patch("portwatcher.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(asyncio.CancelledError):
            await watcher.start_watching()

    assert calls == 2


def test_port_should_be_probed_skips_ignored_ports(tmp_path: Path) -> None:
    device = tmp_path / "ttyUSB0"
    device.touch()
    replugged_device = tmp_path / "ttyUSB1"
    replugged_device.touch()
    link = tmp_path / "usb-device-if00-port0"
    link.symlink_to(device)
    port = MagicMock(device=str(device))
    replugged_port = MagicMock(device=str(replugged_device))
    watcher = PortWatcher(probe_callback=AsyncMock(), found_callback=AsyncMock())

    assert watcher.port_should_be_probed(port)
    watcher.ignored_paths = {str(link)}
    watcher.resolve_ignored_ports()
    assert not watcher.port_should_be_probed(port)
    assert watcher.port_should_be_probed(replugged_port)

    link.unlink()
    link.symlink_to(replugged_device)
    watcher.resolve_ignored_ports()
    assert watcher.port_should_be_probed(port)
    assert not watcher.port_should_be_probed(replugged_port)

    watcher.ignored_paths = {str(device)}
    watcher.resolve_ignored_ports()
    assert not watcher.port_should_be_probed(port)
