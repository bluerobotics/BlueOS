import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterator, Optional, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from autopilot_manager import AutoPilotManager
from flight_controller_detector.Detector import Detector
from flight_controller_detector.serial_by_id import SerialById
from loguru import logger
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
    manager._serial = None
    manager._serial_absence_reported = False
    manager._serial_paths = set()
    manager.autopilot_default_endpoints = []
    manager._heartbeat_burst_pending = False
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


class FakeRouterManager:  # pylint: disable=too-many-instance-attributes
    def __init__(self, lifecycle: Lifecycle, should_be_running: bool = True) -> None:
        self.lifecycle = lifecycle
        self.should_be_running = should_be_running
        self.running = False
        self.restarts = 0
        self.master_endpoint: Optional[Endpoint] = None
        self.endpoints: list[Endpoint] = []

    def add_endpoint(self, endpoint: Endpoint) -> None:
        self.endpoints.append(endpoint)

    @property
    def tool(self) -> MagicMock:
        return MagicMock(exit=self.exit)

    async def exit(self) -> None:
        self.running = False

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


class SerialBoards:
    """Device nodes and by-id links of a fake /dev, so the tests exercise the real filesystem lookups."""

    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "by-id").mkdir()

    def node(self, name: str) -> str:
        path = self.root / name
        path.touch()
        return str(path)

    def link(self, node: str, name: str = "usb-ArduPilot_Pixhawk1_123-if00") -> str:
        link = self.root / "by-id" / name
        link.unlink(missing_ok=True)
        link.symlink_to(node)
        return str(link)

    def remove(self, node: str, link: Optional[str] = None) -> None:
        Path(node).unlink()
        if link:
            Path(link).unlink()


@pytest.fixture(name="dev")
def fixture_dev(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SerialBoards:
    monkeypatch.setattr(SerialById, "BY_ID_DIR", tmp_path / "by-id")
    return SerialBoards(tmp_path)


def pixhawk_at(
    path: str, name: str = "Pixhawk1", flags: Optional[list[FlightControllerFlags]] = None
) -> FlightController:
    return FlightController(name=name, platform=Platform.Pixhawk1, path=path, flags=flags or [])


def serial_board_on(
    manager: AutoPilotManager, lifecycle: Lifecycle, board: FlightController, link: Optional[str] = None
) -> FakeRouterManager:
    router = FakeRouterManager(lifecycle)
    router.running = True
    router.master_endpoint = AutoPilotManager._serial_master_endpoint(board)
    manager.mavlink_manager = cast(Manager, router)
    manager._current_board = board
    manager._serial_paths = {board.path or ""}
    manager._serial = SerialById(board.path or "")
    assert link is None or manager._serial.link == link
    return router


def detected_serial_boards(*boards: FlightController) -> Any:
    return patch.object(Detector, "detect_serial_flight_controllers", MagicMock(return_value=list(boards)))


@pytest.mark.parametrize("old_node_stays", [False, True])
async def test_router_watchdog_follows_serial_board_to_its_new_path(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards, old_node_stays: bool
) -> None:
    old = dev.node("ttyACM0")
    link = dev.link(old)
    router = serial_board_on(manager, lifecycle, pixhawk_at(old), link)
    new = dev.node("ttyACM1")
    dev.link(new)
    if not old_node_stays:
        Path(old).unlink()

    await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert router.master_endpoint is not None and router.master_endpoint.place == new
    assert manager.current_board == pixhawk_at(new)
    assert manager._serial is not None and manager._serial.link == link


async def test_router_watchdog_gives_the_default_endpoints_to_a_new_manager_it_restarts(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    old = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(old), dev.link(old))
    manager.autopilot_default_endpoints = [MASTER]
    Path(old).unlink()
    dev.link(dev.node("ttyACM1"))

    await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert router.endpoints == [MASTER]


async def test_router_watchdog_leaves_present_serial_board_alone(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node), dev.link(node))

    with detected_serial_boards() as detect:
        await manager._restart_router_if_dead()

    detect.assert_not_called()
    assert router.restarts == 0


async def test_without_a_link_a_single_candidate_is_the_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    old = str(dev.root / "ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(old))
    bootloader = pixhawk_at("/dev/ttyACM1", "Pixhawk1-BL", [FlightControllerFlags.is_bootloader])
    other_platform = FlightController(name="Pixhawk4", platform=Platform.Pixhawk4, path="/dev/ttyACM2")
    moved = pixhawk_at(str(dev.root / "ttyACM3"))

    with detected_serial_boards(bootloader, other_platform, moved):
        await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert manager.current_board == moved


@pytest.mark.parametrize("candidates", [0, 2])
async def test_without_a_link_it_does_not_guess(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards, candidates: int
) -> None:
    router = serial_board_on(manager, lifecycle, pixhawk_at(str(dev.root / "ttyACM0")))
    router.running = True

    with detected_serial_boards(*[pixhawk_at(str(dev.root / f"ttyACM{i + 1}")) for i in range(candidates)]):
        await manager._restart_router_if_dead()

    assert not router.running
    assert router.restarts == 0


async def test_without_a_link_several_candidates_are_reported_once(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    serial_board_on(manager, lifecycle, pixhawk_at(str(dev.root / "ttyACM0")))
    messages: list[str] = []
    sink = logger.add(lambda message: messages.append(str(message)), level="WARNING")
    try:
        with detected_serial_boards(pixhawk_at("/dev/ttyACM1"), pixhawk_at("/dev/ttyACM2")):
            await manager._restart_router_if_dead()
            await manager._restart_router_if_dead()
    finally:
        logger.remove(sink)

    assert len([message for message in messages if "Several Pixhawk1 boards" in message]) == 1


async def test_without_a_link_a_present_board_is_not_searched_for(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    router = serial_board_on(manager, lifecycle, pixhawk_at(dev.node("ttyACM0")))

    with detected_serial_boards() as detect:
        await manager._restart_router_if_dead()

    detect.assert_not_called()
    assert router.restarts == 0


async def test_router_watchdog_waits_for_the_serial_board_without_touching_its_old_path(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    old = dev.node("ttyACM0")
    link = dev.link(old)
    router = serial_board_on(manager, lifecycle, pixhawk_at(old), link)
    dev.remove(old, link)

    # The router died too: it must not be restarted on a path that is gone
    router.running = False
    await manager._restart_router_if_dead()
    await manager._restart_router_if_dead()
    assert router.restarts == 0 and manager.current_board == pixhawk_at(old)

    new = dev.node("ttyACM1")
    dev.link(new)
    await manager._restart_router_if_dead()
    assert router.restarts == 1
    assert router.master_endpoint is not None and router.master_endpoint.place == new


async def test_router_watchdog_reports_each_absence_of_the_serial_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    link = dev.link(node)
    serial_board_on(manager, lifecycle, pixhawk_at(node), link)
    Path(link).unlink()
    await manager._restart_router_if_dead()
    assert manager._serial_absence_reported

    dev.link(node)
    await manager._restart_router_if_dead()
    assert not manager._serial_absence_reported


async def test_router_watchdog_keeps_the_board_current_when_the_router_fails_to_start(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    old = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(old), dev.link(old))
    Path(old).unlink()
    new = dev.node("ttyACM1")
    dev.link(new)
    router.restart = AsyncMock(side_effect=RuntimeError("router failed to start"))  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await manager._restart_router_if_dead()

    assert manager.current_board == pixhawk_at(new)


async def test_router_watchdog_reports_a_second_absence_after_a_start(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    link = dev.link(node)
    serial_board_on(manager, lifecycle, pixhawk_at(node), link)
    manager._serial_absence_reported = True

    manager.start_mavlink_manager = AsyncMock()  # type: ignore[method-assign]
    manager.vehicle_manager = AsyncMock()
    await manager.start_serial(pixhawk_at(node))

    assert not manager._serial_absence_reported


async def test_router_watchdog_stops_a_router_whose_path_went_to_another_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    old = dev.node("ttyACM0")
    link = dev.link(old)
    router = serial_board_on(manager, lifecycle, pixhawk_at(old), link)
    Path(link).unlink()  # our board is gone, ttyACM0 now belongs to another one

    await manager._restart_router_if_dead()

    assert not router.running and router.restarts == 0
    assert router.should_be_running, "the intent to run must be kept"


async def test_dangling_by_id_link_at_the_master_place_reads_as_left(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node), dev.link(node))
    Path(node).unlink()  # udev has not removed the link yet

    await manager._restart_router_if_dead()

    assert not router.running and router.restarts == 0
    assert manager._serial_absence_reported


@pytest.mark.parametrize("absent, restarts", [(True, 0), (False, 1)])
async def test_heartbeat_watchdog_does_not_restart_while_the_serial_board_is_absent(
    manager: AutoPilotManager, absent: bool, restarts: int
) -> None:
    manager._serial_absence_reported = absent
    manager.should_be_running = True
    manager._start_fail_count = 0
    manager._heartbeat_fail_count = 9
    manager._max_heartbeat_failures = 10
    manager.vehicle_manager = AsyncMock()
    manager.vehicle_manager.is_heart_beating.return_value = False
    restart = AsyncMock()
    manager.restart_ardupilot = restart  # type: ignore[method-assign]

    with (
        patch.object(manager, "is_running", return_value=True),
        patch("autopilot_manager.asyncio.sleep", AsyncMock(side_effect=StopAsyncIteration)),
        pytest.raises(StopAsyncIteration),
    ):
        await manager.auto_restart_ardupilot()

    assert restart.await_count == restarts


async def test_setup_forgets_the_absence_of_the_serial_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    serial_board_on(manager, lifecycle, pixhawk_at(node), dev.link(node))
    manager._serial_absence_reported = manager._heartbeat_burst_pending = True
    manager.mavlink_manager.stop = AsyncMock()  # type: ignore[method-assign]

    with (
        patch("autopilot_manager.MavlinkManager"),
        patch("autopilot_manager.FirmwareManager"),
        patch("autopilot_manager.VehicleManager"),
        patch.multiple(
            manager,
            load_preferred_router=MagicMock(return_value="MAVLink-Server"),
            load_tlog_mode=MagicMock(),
            load_sitl_frame=MagicMock(),
            _load_endpoints=MagicMock(),
            remove_old_logs=MagicMock(),
        ),
    ):
        await manager.setup()

    assert not manager._serial_absence_reported
    assert manager._serial is None
    assert not manager._heartbeat_burst_pending


async def test_router_watchdog_does_not_move_stopped_serial_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node), dev.link(node))
    router.should_be_running = router.running = False
    dev.link(dev.node("ttyACM1"))

    await manager._restart_router_if_dead()

    assert router.restarts == 0 and not router.running


async def test_router_watchdog_does_not_override_manual_master_endpoint(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node), dev.link(node))
    router.master_endpoint = MASTER
    router.running = False
    dev.link(dev.node("ttyACM1"))

    await manager._restart_router_if_dead()

    assert router.master_endpoint == MASTER
    assert manager.current_board == pixhawk_at(node)


async def test_router_watchdog_leaves_a_serial_master_on_another_node_alone(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node, other = dev.node("ttyACM0"), dev.node("ttyACM1")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node), dev.link(node))
    router.master_endpoint = AutoPilotManager._serial_master_endpoint(pixhawk_at(other))
    router.running = False

    await manager._restart_router_if_dead()

    assert router.master_endpoint.place == other
    assert manager.current_board == pixhawk_at(node)


async def test_start_serial_looks_up_the_by_id_link_each_time(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    serial_board_on(manager, lifecycle, pixhawk_at("/dev/ttyACM9"))
    manager.start_mavlink_manager = AsyncMock()  # type: ignore[method-assign]
    manager.vehicle_manager = AsyncMock()
    first, second = dev.node("ttyACM0"), dev.node("ttyACM1")
    link = dev.link(first)

    await manager.start_serial(pixhawk_at(first))
    assert manager._serial is not None and manager._serial.link == link
    Path(link).unlink()
    await manager.start_serial(pixhawk_at(second))
    assert manager._serial is not None and not manager._serial.link


def test_serial_master_endpoint_needs_a_path() -> None:
    with pytest.raises(ValueError):
        AutoPilotManager._serial_master_endpoint(FlightController(name="Pixhawk1", platform=Platform.Pixhawk1))


PX4 = "PX4 FMU v2.x"  # What PX4 reports as USB product, identified as a Pixhawk1


@pytest.mark.parametrize("board_name, bursts", [(PX4, 1), ("Pixhawk1", 0)])
async def test_router_watchdog_wakes_up_moved_px4_board(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards, board_name: str, bursts: int
) -> None:
    old = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(old, board_name), dev.link(old))
    manager.vehicle_manager = AsyncMock()
    manager.vehicle_manager.is_heart_beating.return_value = False
    Path(old).unlink()
    dev.link(dev.node("ttyACM1"))

    await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert manager.vehicle_manager.burst_heartbeat.await_count == bursts


@pytest.mark.parametrize("board_name, bursts", [(PX4, 1), ("Pixhawk1", 0)])
async def test_router_watchdog_wakes_up_px4_board_after_restarting_on_the_same_path(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards, board_name: str, bursts: int
) -> None:
    node = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node, board_name), dev.link(node))
    router.running = False
    manager.vehicle_manager = AsyncMock()
    manager.vehicle_manager.is_heart_beating.return_value = False
    locked_while_bursting = []

    async def burst() -> None:
        locked_while_bursting.append(manager._lifecycle_lock.locked())

    manager.vehicle_manager.burst_heartbeat = burst

    await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert locked_while_bursting == [False] * bursts


async def test_router_watchdog_repeats_px4_wake_up_until_the_vehicle_is_heard(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    router = serial_board_on(manager, lifecycle, pixhawk_at(node, PX4), dev.link(node))
    router.running = False
    manager.vehicle_manager = AsyncMock()
    manager.vehicle_manager.burst_heartbeat.side_effect = [RuntimeError("mavlink2rest is not up yet"), None]
    manager.vehicle_manager.is_heart_beating.side_effect = [False, False, True]

    await manager._restart_router_if_dead()  # restarts, the burst fails
    await manager._restart_router_if_dead()  # still silent, bursts again
    await manager._restart_router_if_dead()  # heard, done
    await manager._restart_router_if_dead()

    assert router.restarts == 1
    assert manager.vehicle_manager.burst_heartbeat.await_count == 2
    assert manager.vehicle_manager.is_heart_beating.await_count == 3
    assert not manager._heartbeat_burst_pending


async def test_px4_wake_up_gives_up_on_a_silent_vehicle_until_requested_again(
    manager: AutoPilotManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(AutoPilotManager, "HEARTBEAT_BURST_MAX_RETRIES", 3)
    manager.vehicle_manager = AsyncMock()
    manager.vehicle_manager.is_heart_beating.return_value = False
    bursts = manager.vehicle_manager.burst_heartbeat

    await manager._wake_up_px4(pixhawk_at("/dev/ttyACM0", PX4))
    for _ in range(5):
        await manager._retry_heartbeat_burst()

    assert bursts.await_count == 1 + 3
    assert not manager._heartbeat_burst_pending

    await manager._wake_up_px4(pixhawk_at("/dev/ttyACM0", PX4))
    await manager._retry_heartbeat_burst()
    assert bursts.await_count == 1 + 3 + 1 + 1
    assert manager._heartbeat_burst_pending


async def test_px4_wake_up_retry_does_not_hold_the_lifecycle_lock(
    manager: AutoPilotManager, lifecycle: Lifecycle, dev: SerialBoards
) -> None:
    node = dev.node("ttyACM0")
    serial_board_on(manager, lifecycle, pixhawk_at(node, PX4), dev.link(node))
    manager._heartbeat_burst_pending = True
    manager.vehicle_manager = AsyncMock()
    locked_while_waiting = []

    async def is_heart_beating() -> bool:
        locked_while_waiting.append(manager._lifecycle_lock.locked())
        return True

    manager.vehicle_manager.is_heart_beating = is_heart_beating
    await manager._restart_router_if_dead()

    assert locked_while_waiting == [False]
