import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator, Optional, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autopilot_manager import AutoPilotManager
from flight_controller_detector.Detector import Detector
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.Manager import Manager
from typedefs import FlightController, FlightControllerFlags, Platform, PlatformType

pytestmark = [pytest.mark.asyncio, pytest.mark.timeout(5)]

SITL = FlightController(name="SITL", platform=Platform.SITL)
MASTER = Endpoint(name="Master", owner="Test", connection_type=EndpointType.UDPServer, place="0.0.0.0", argument=14551)


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
    manager._serial_board_usb_serial_number = None
    manager._settings_manager = MagicMock()
    manager.firmware_manager = AsyncMock()
    manager.mavlink_manager = MagicMock(
        should_be_running=True,
        is_running=AsyncMock(return_value=False),
        restart=lambda: lifecycle.step("restart_router"),
    )
    with (
        patch.object(manager, "_kill_ardupilot_locked", lambda: lifecycle.step("kill")),
        patch.object(manager, "_start_ardupilot_locked", lambda: lifecycle.step("start")),
        patch.object(manager, "_set_preferred_router_locked", lambda *_: lifecycle.step("set_preferred_router")),
        patch.object(AutoPilotManager, "available_boards", AsyncMock(return_value=[SITL])),
    ):
        yield manager


OPERATIONS: dict[str, Callable[[AutoPilotManager], Awaitable[Any]]] = {
    "kill": lambda manager: manager.kill_ardupilot(),
    "start": lambda manager: manager.start_ardupilot(),
    "restart": lambda manager: manager.restart_ardupilot(),
    "change_board": lambda manager: manager.change_board(SITL),
    "add_endpoints": lambda manager: manager.add_new_endpoints(set()),
    "remove_endpoints": lambda manager: manager.remove_endpoints(set()),
    "update_endpoints": lambda manager: manager.update_endpoints(set()),
    "set_manual_board_master_endpoint": lambda manager: manager.set_manual_board_master_endpoint(MASTER),
    "install_from_file": lambda manager: manager.install_firmware_from_file(Path("firmware"), SITL),
    "install_from_url": lambda manager: manager.install_firmware_from_url("https://example.invalid/fw", SITL),
    "restore_default": lambda manager: manager.restore_default_firmware(SITL),
    "set_preferred_router": lambda manager: manager.set_preferred_router("MAVLink-Server"),
    "router_watchdog": lambda manager: manager._restart_router_if_dead(),
}


async def test_concurrent_operations_never_overlap(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    await asyncio.gather(*[operation(manager) for operation in OPERATIONS.values()] * 3)

    assert lifecycle.max_running == 1
    assert not manager._lifecycle_lock.locked()


async def test_failed_install_starts_autopilot_again(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    failing_download = AsyncMock(side_effect=RuntimeError("download failed"))
    with patch.object(manager.firmware_manager, "install_firmware_from_url", failing_download):
        with pytest.raises(RuntimeError):
            await manager.install_firmware_from_url("https://example.invalid/fw", SITL)

    assert lifecycle.calls == ["kill", "start"]
    assert not manager._lifecycle_lock.locked()


class FakeRouterManager:
    def __init__(self, lifecycle: Lifecycle, should_be_running: bool = True) -> None:
        self.lifecycle = lifecycle
        self.should_be_running = should_be_running
        self.running = False
        self.restarts = 0
        self.master_endpoint: Optional[Endpoint] = None

    async def is_running(self) -> bool:
        return self.running

    async def restart(self, master_endpoint: Optional[Endpoint] = None) -> None:
        await self.lifecycle.step("restart_router")
        if master_endpoint:
            self.master_endpoint = master_endpoint
        self.restarts += 1
        self.running = True
        self.should_be_running = True

    async def stop(self) -> None:
        await self.lifecycle.step("stop_router")
        self.should_be_running = False
        self.running = False


async def test_router_watchdog_follows_current_manager(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    old_router = FakeRouterManager(lifecycle, should_be_running=False)
    manager.mavlink_manager = cast(Manager, old_router)
    watchdog = asyncio.create_task(manager.start_mavlink_manager_watchdog(interval=0.01))
    await asyncio.sleep(0.05)

    # What setup() does on every start
    new_router = FakeRouterManager(lifecycle)
    manager.mavlink_manager = cast(Manager, new_router)
    await asyncio.sleep(0.05)
    watchdog.cancel()

    assert new_router.restarts == 1
    assert old_router.restarts == 0


async def test_router_watchdog_skips_while_locked(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    router = FakeRouterManager(lifecycle)
    manager.mavlink_manager = cast(Manager, router)
    async with manager._lifecycle_lock:
        await manager._restart_router_if_dead()
    assert router.restarts == 0

    await manager._restart_router_if_dead()
    assert router.restarts == 1


async def test_router_watchdog_does_not_revive_stopped_router(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    router = FakeRouterManager(lifecycle)
    manager.mavlink_manager = cast(Manager, router)

    async def kill() -> None:
        async with manager._lifecycle_lock:
            await router.stop()

    # Watchdog first: it restarts the dead router, then the stop wins
    await asyncio.gather(manager._restart_router_if_dead(), kill())
    assert not router.should_be_running and not router.running

    # Stop first: the watchdog sees the user's intent and leaves it down
    router.should_be_running = True
    await asyncio.gather(kill(), manager._restart_router_if_dead())
    assert not router.should_be_running and not router.running
    assert lifecycle.max_running == 1


async def test_router_watchdog_survives_exceptions(manager: AutoPilotManager) -> None:
    restart = AsyncMock(side_effect=[RuntimeError("router failed to start"), None])
    manager.mavlink_manager = MagicMock(
        should_be_running=True, is_running=AsyncMock(return_value=False), restart=restart
    )
    watchdog = asyncio.create_task(manager.start_mavlink_manager_watchdog(interval=0.01))
    await asyncio.sleep(0.1)

    assert not watchdog.done()
    assert restart.await_count >= 2
    watchdog.cancel()


async def test_failed_router_restart_keeps_retrying(manager: AutoPilotManager) -> None:
    router = Manager.__new__(Manager)
    router.tool = MagicMock(
        restart=AsyncMock(side_effect=RuntimeError("boom")), is_running=AsyncMock(return_value=False)
    )
    router.should_be_running = True
    router._last_valid_endpoints = set()
    manager.mavlink_manager = router

    with pytest.raises(RuntimeError):
        await manager._restart_router_if_dead()
    assert router.should_be_running, "a failed restart must not disarm the watchdog"


async def test_serial_restart_holds_router_watchdog(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    router = FakeRouterManager(lifecycle)
    manager.mavlink_manager = cast(Manager, router)
    manager._current_board = FlightController(name="Pixhawk", platform=Platform.Pixhawk1, path="/dev/ttyACM0")
    assert manager._current_board.type == PlatformType.Serial
    manager.vehicle_manager = AsyncMock()
    board_dropped = asyncio.Event()

    async def detect(_board: FlightController) -> None:
        board_dropped.set()
        await asyncio.sleep(1)  # board never comes back during the test
        return None

    with patch.object(manager, "_detect_serial_board", detect):
        restart = asyncio.create_task(manager.restart_ardupilot())
        await board_dropped.wait()
        assert not router.should_be_running
        await manager._restart_router_if_dead()
        restart.cancel()

    assert router.restarts == 0


async def test_endpoint_change_does_not_start_stopped_router(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    router = FakeRouterManager(lifecycle, should_be_running=False)
    router.add_endpoints = MagicMock()  # type: ignore[attr-defined]
    manager.mavlink_manager = cast(Manager, router)
    manager._save_current_endpoints = MagicMock()  # type: ignore[method-assign]

    await manager.add_new_endpoints(set())

    assert router.restarts == 0
    assert not router.should_be_running


PIXHAWK = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1, path="/dev/ttyACM0")


def serial_board_on(
    manager: AutoPilotManager, lifecycle: Lifecycle, should_be_running: bool = True
) -> FakeRouterManager:
    router = FakeRouterManager(lifecycle, should_be_running)
    router.running = should_be_running
    router.master_endpoint = AutoPilotManager._serial_master_endpoint(PIXHAWK)
    manager.mavlink_manager = cast(Manager, router)
    manager._current_board = PIXHAWK
    manager._serial_board_usb_serial_number = "ours"
    return router


def detected_serial_boards(*boards: FlightController) -> Any:
    return patch.object(Detector, "detect_serial_flight_controllers", MagicMock(return_value=list(boards)))


async def test_router_watchdog_follows_moved_serial_board(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    router = serial_board_on(manager, lifecycle)
    bootloader = FlightController(
        name="Pixhawk1-BL", platform=Platform.Pixhawk1, path="/dev/ttyACM1", flags=[FlightControllerFlags.is_bootloader]
    )
    other_board = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1, path="/dev/ttyACM2")
    moved_board = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1, path="/dev/ttyACM3")
    usb_serial_numbers = {"/dev/ttyACM1": "ours", "/dev/ttyACM2": "other", "/dev/ttyACM3": "ours"}

    with (
        patch("os.path.exists", MagicMock(return_value=False)),
        detected_serial_boards(bootloader, other_board, moved_board),
        patch.object(Detector, "usb_serial_numbers", MagicMock(return_value=usb_serial_numbers)),
    ):
        await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert router.master_endpoint is not None and router.master_endpoint.place == "/dev/ttyACM3"
    assert manager.current_board == moved_board


async def test_router_watchdog_waits_for_missing_serial_board(manager: AutoPilotManager, lifecycle: Lifecycle) -> None:
    router = serial_board_on(manager, lifecycle)
    bootloader = FlightController(
        name="Pixhawk1-BL", platform=Platform.Pixhawk1, path="/dev/ttyACM1", flags=[FlightControllerFlags.is_bootloader]
    )

    with patch("os.path.exists", MagicMock(return_value=False)), detected_serial_boards(bootloader):
        await manager._restart_router_if_dead()

    assert router.restarts == 0
    assert manager.current_board == PIXHAWK


async def test_router_watchdog_does_not_scan_present_serial_board(
    manager: AutoPilotManager, lifecycle: Lifecycle
) -> None:
    router = serial_board_on(manager, lifecycle)

    with patch("os.path.exists", MagicMock(return_value=True)), detected_serial_boards() as detect:
        await manager._restart_router_if_dead()

    detect.assert_not_called()
    assert router.restarts == 0


async def test_router_watchdog_does_not_move_stopped_serial_board(
    manager: AutoPilotManager, lifecycle: Lifecycle
) -> None:
    router = serial_board_on(manager, lifecycle, should_be_running=False)
    moved_board = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1, path="/dev/ttyACM1")

    with patch("os.path.exists", MagicMock(return_value=False)), detected_serial_boards(moved_board) as detect:
        await manager._restart_router_if_dead()

    detect.assert_not_called()
    assert router.restarts == 0 and not router.running


@pytest.mark.parametrize(
    "board_name, bursts",
    [("PX4 FMU v2.x", 1), ("Pixhawk1", 0)],
)
async def test_router_watchdog_wakes_up_moved_px4_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, board_name: str, bursts: int
) -> None:
    router = serial_board_on(manager, lifecycle)
    manager._current_board = FlightController(name=board_name, platform=Platform.Pixhawk1, path="/dev/ttyACM0")
    manager.vehicle_manager = AsyncMock()
    moved_board = FlightController(name=board_name, platform=Platform.Pixhawk1, path="/dev/ttyACM1")

    with (
        patch("os.path.exists", MagicMock(return_value=False)),
        detected_serial_boards(moved_board),
        patch.object(Detector, "usb_serial_numbers", MagicMock(return_value={"/dev/ttyACM1": "ours"})),
    ):
        await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert router.master_endpoint is not None and router.master_endpoint.place == "/dev/ttyACM1"
    assert manager.vehicle_manager.burst_heartbeat.await_count == bursts


async def test_router_watchdog_does_not_follow_another_serial_board(
    manager: AutoPilotManager, lifecycle: Lifecycle
) -> None:
    router = serial_board_on(manager, lifecycle)
    other_board = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1, path="/dev/ttyACM1")

    with (
        patch("os.path.exists", MagicMock(return_value=False)),
        detected_serial_boards(other_board),
        patch.object(Detector, "usb_serial_numbers", MagicMock(return_value={"/dev/ttyACM1": "other"})),
    ):
        await manager._restart_router_if_dead()

    assert router.restarts == 0
    assert manager.current_board == PIXHAWK
    assert manager._serial_board_usb_serial_number == "ours"


async def test_router_watchdog_follows_serial_board_without_serial_number(
    manager: AutoPilotManager, lifecycle: Lifecycle
) -> None:
    router = serial_board_on(manager, lifecycle)
    manager._serial_board_usb_serial_number = None
    moved_board = FlightController(name="Pixhawk1", platform=Platform.Pixhawk1, path="/dev/ttyACM1")

    with (
        patch("os.path.exists", MagicMock(return_value=False)),
        detected_serial_boards(moved_board),
        patch.object(Detector, "usb_serial_numbers", MagicMock(return_value={"/dev/ttyACM1": "found"})),
    ):
        await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert manager.current_board == moved_board
    assert manager._serial_board_usb_serial_number == "found"


def test_serial_master_endpoint_needs_a_path() -> None:
    with pytest.raises(ValueError):
        AutoPilotManager._serial_master_endpoint(FlightController(name="Pixhawk1", platform=Platform.Pixhawk1))
