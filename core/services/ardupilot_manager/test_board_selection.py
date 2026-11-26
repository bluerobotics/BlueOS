import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import flight_controller_detector.Detector as detector_module
import psutil
import pytest
from autopilot_manager import AutoPilotManager, board_matches_preferred
from flight_controller_detector.Detector import Detector
from typedefs import FlightController, Platform, PlatformType

pytestmark = pytest.mark.asyncio

NAVIGATOR = FlightController(name="Navigator", platform=Platform(name="Navigator", platform_type=PlatformType.Linux))
SITL = FlightController(name="SITL", platform=Platform.SITL())
MANUAL = Detector.detect_manual()
PIXHAWK1 = FlightController(
    name="PX4 FMU v2.x",
    manufacturer="3D Robotics",
    platform=Platform(name="Pixhawk1", platform_type=PlatformType.Serial),
    ardupilot_board_id=9,
    path="/dev/ttyACM1",
)


def manager_with(preferred_board: Optional[FlightController] = None) -> AutoPilotManager:
    manager = AutoPilotManager.__new__(AutoPilotManager)
    manager._settings_manager = MagicMock(settings=SimpleNamespace(preferred_board=preferred_board))
    manager._current_board = None
    manager._lifecycle_lock = asyncio.Lock()
    return manager


def legacy_board(**data: Any) -> FlightController:
    return FlightController.model_validate({"path": "/dev/ttyACM0", "flags": [], **data})


async def test_manual_and_sitl_are_never_auto_selected() -> None:
    manager = manager_with()
    with pytest.raises(RuntimeError):
        manager.get_board_to_be_used([MANUAL, SITL])
    assert manager.get_board_to_be_used([MANUAL, SITL, NAVIGATOR]) == NAVIGATOR


async def test_serial_board_preferred_over_linux_board() -> None:
    manager = manager_with()
    assert manager.get_board_to_be_used([MANUAL, NAVIGATOR, PIXHAWK1]) == PIXHAWK1


async def test_legacy_preferred_board_matches_detected_board() -> None:
    preferred = legacy_board(name="PX4 FMU v2.x", platform="Pixhawk1")
    assert preferred.ardupilot_board_id is None
    manager = manager_with(preferred)
    assert manager.get_board_to_be_used([NAVIGATOR, MANUAL, PIXHAWK1]) == PIXHAWK1


async def test_preferred_manual_and_linux_boards_match_by_platform() -> None:
    boards = [PIXHAWK1, NAVIGATOR, MANUAL]
    assert manager_with(legacy_board(name="Manual", platform="Manual")).get_board_to_be_used(boards) == MANUAL
    assert manager_with(legacy_board(name="Navigator", platform="navigator")).get_board_to_be_used(boards) == NAVIGATOR


def test_board_matching_rules() -> None:
    assert board_matches_preferred(PIXHAWK1, PIXHAWK1.model_copy(update={"path": "/dev/ttyACM3", "name": "Pixhawk1"}))
    assert not board_matches_preferred(PIXHAWK1, PIXHAWK1.model_copy(update={"ardupilot_board_id": 50}))
    assert not board_matches_preferred(PIXHAWK1, NAVIGATOR)
    lowercase = PIXHAWK1.model_copy(update={"platform": Platform(name="pixhawk1", platform_type=PlatformType.Serial)})
    assert board_matches_preferred(lowercase, PIXHAWK1)

    generic = legacy_board(name="PX4 FMU v2.x", platform="GenericSerial")
    assert board_matches_preferred(generic, PIXHAWK1)
    assert not board_matches_preferred(generic, PIXHAWK1.model_copy(update={"name": "MatekH743"}))

    legacy = legacy_board(name="PX4 FMU v2.x", platform="Pixhawk1")
    assert board_matches_preferred(legacy, PIXHAWK1.model_copy(update={"name": "Pixhawk1"}))
    assert not board_matches_preferred(legacy, NAVIGATOR.model_copy(update={"name": "PX4 FMU v2.x"}))


def test_legacy_cube_orange_plus_matches_after_upgrade() -> None:
    # Older versions matched "CubeOrange" as a substring of the USB product, so they saved this for a CubeOrange+
    preferred = legacy_board(name="CubeOrange+", platform="CubeOrange")
    detected = FlightController(
        name="CubeOrange+",
        manufacturer="CubePilot",
        platform=Platform(name="CubeOrangePlus", platform_type=PlatformType.Serial),
        ardupilot_board_id=1063,
        path="/dev/ttyACM0",
    )
    assert board_matches_preferred(preferred, detected)
    other_cube = detected.model_copy(update={"name": "Other", "path": "/dev/ttyACM1"})
    assert manager_with(preferred).get_board_to_be_used([NAVIGATOR, other_cube, detected]) == detected
    assert not board_matches_preferred(preferred, detected.model_copy(update={"name": "CubeOrangePlus"}))
    # Boards saved with a board id are matched by board id and platform only
    saved = detected.model_copy(update={"name": "Other"})
    assert board_matches_preferred(saved, detected)
    assert not board_matches_preferred(saved, detected.model_copy(update={"ardupilot_board_id": 140}))


async def test_change_board_accepts_board_matching_detected_one() -> None:
    manager = manager_with()
    manager.set_preferred_board = MagicMock()  # type: ignore[method-assign]
    with (
        patch.object(manager, "available_boards", AsyncMock(return_value=[PIXHAWK1])),
        patch.object(manager, "_kill_ardupilot_locked", AsyncMock()),
        patch.object(manager, "_start_ardupilot_locked", AsyncMock()),
    ):
        await manager.change_board(legacy_board(name="PX4 FMU v2.x", platform="Pixhawk1"))
        with pytest.raises(ValueError):
            await manager.change_board(NAVIGATOR)


def fake_port(device: str) -> SimpleNamespace:
    return SimpleNamespace(
        device=device,
        name=device.rsplit("/", 1)[-1],
        vid=0x26AC,
        pid=0x0011,
        product="PX4 FMU v2.x",
        manufacturer="3D Robotics",
        serial_number="1234",
        usb_device_path="/sys/devices/usb1/1-1",
        location="1-1:1.0",
    )


async def test_detect_serial_board_follows_the_port(monkeypatch: pytest.MonkeyPatch) -> None:
    ports: List[SimpleNamespace] = [fake_port("/dev/ttyACM1")]
    probed: List[str] = []

    async def get_board_id(device: str) -> int:
        probed.append(device)
        return 9

    monkeypatch.setattr(detector_module, "comports", lambda: ports)
    monkeypatch.setattr(detector_module, "get_board_id", get_board_id)
    monkeypatch.setattr(detector_module, "is_running_as_root", lambda: False)
    manager = manager_with()
    manager._current_board = PIXHAWK1

    assert await manager._detect_serial_board(PIXHAWK1) == PIXHAWK1
    assert not probed, "the running board's port must not be probed"

    ports.clear()
    assert await manager._detect_serial_board(PIXHAWK1) is None

    ports.append(fake_port("/dev/ttyACM2"))
    reconnected = await manager._detect_serial_board(PIXHAWK1)
    assert reconnected is not None
    assert reconnected.path == "/dev/ttyACM2"
    assert probed == ["/dev/ttyACM2"]
    Detector.invalidate_caches()


def test_running_ardupilot_processes_matches_any_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    def process(*cmdline: str, error: Optional[Exception] = None) -> MagicMock:
        fake = MagicMock()
        fake.cmdline.side_effect = error
        fake.cmdline.return_value = list(cmdline)
        return fake

    navigator = process("/bin/sh", "-c", "/fw/ardupilot_navigator -A udp:127.0.0.1:8852")
    sitl = process("/fw/ardupilot_sitl_x86_64_linux_gnu", "--model", "vectored")
    processes = [
        navigator,
        sitl,
        process("/usr/bin/python3", "main.py"),
        process(error=psutil.NoSuchProcess(1)),
        process(error=psutil.AccessDenied(2)),
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda: processes)
    manager = manager_with()
    manager.firmware_manager = MagicMock(firmware_folder=Path("/fw"))

    assert manager.running_ardupilot_processes() == [navigator, sitl]
