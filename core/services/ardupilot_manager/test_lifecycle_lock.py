import asyncio
import sys
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# commonwealth is not installed in the 1.4 test env, so it is loaded by path
sys.path.append(str(Path(__file__).resolve().parents[2] / "libs" / "commonwealth"))

from autopilot_manager import AutoPilotManager
from typedefs import FlightController, Platform

pytestmark = [pytest.mark.asyncio, pytest.mark.timeout(5)]

SITL = FlightController(name="SITL", platform=Platform.SITL)


class Lifecycle:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.calls: list[str] = []
        self.running = 0
        self.max_running = 0

    async def step(self, name: str) -> None:
        assert self.lock.locked(), f"{name} called without holding the lifecycle lock"
        self.calls.append(name)
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        await asyncio.sleep(0.01)
        self.running -= 1


@pytest.fixture(name="lifecycle")
def fixture_lifecycle() -> Lifecycle:
    return Lifecycle()


@pytest.fixture(name="manager")
def fixture_manager(lifecycle: Lifecycle) -> Iterator[AutoPilotManager]:
    manager = AutoPilotManager.__new__(AutoPilotManager)
    manager._lifecycle_lock = lifecycle.lock
    manager._current_board = None
    manager.settings = MagicMock()
    manager.configuration = {}
    manager.firmware_manager = MagicMock()
    with (
        patch.object(manager, "_kill_ardupilot_locked", lambda: lifecycle.step("kill")),
        patch.object(manager, "_start_ardupilot_locked", lambda: lifecycle.step("start")),
        patch.object(AutoPilotManager, "available_boards", AsyncMock(return_value=[SITL])),
    ):
        yield manager


OPERATIONS: dict[str, Callable[[AutoPilotManager], Awaitable[Any]]] = {
    "kill": lambda manager: manager.kill_ardupilot(),
    "start": lambda manager: manager.start_ardupilot(),
    "restart": lambda manager: manager.restart_ardupilot(),
    "change_board": lambda manager: manager.change_board(SITL),
    "install_from_file": lambda manager: manager.install_firmware_from_file(Path("firmware"), SITL),
    "install_from_url": lambda manager: manager.install_firmware_from_url("https://example.invalid/fw", SITL),
    "restore_default": lambda manager: manager.restore_default_firmware(SITL),
}


async def test_concurrent_operations_never_overlap(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    await asyncio.gather(*[operation(manager) for operation in OPERATIONS.values()] * 3)

    assert lifecycle.max_running == 1
    assert not manager._lifecycle_lock.locked()


async def test_failed_install_starts_autopilot_again(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    failing_download = MagicMock(side_effect=RuntimeError("download failed"))
    with patch.object(manager.firmware_manager, "install_firmware_from_url", failing_download):
        with pytest.raises(RuntimeError):
            await manager.install_firmware_from_url("https://example.invalid/fw", SITL)

    assert lifecycle.calls == ["kill", "start"]
    assert not manager._lifecycle_lock.locked()
