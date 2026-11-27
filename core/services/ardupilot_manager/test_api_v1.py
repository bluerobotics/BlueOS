import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock

import flight_controller_detector.Detector as detector_module
import httpx
import pytest
from autopilot_manager import AutoPilotManager
from commonwealth.utils.Singleton import Singleton
from exceptions import InvalidFirmwareFile
from fastapi import FastAPI
from firmware.install_job import FirmwareInstallJobManager, OutputCallback
from flight_controller_detector.Detector import Detector
from pydantic import TypeAdapter
from typedefs import FlightController, FlightControllerFlags, Platform, PlatformType

# Importing the routers instantiates the AutoPilotManager singleton, which touches the real settings and folders
_stub_manager = AutoPilotManager.__new__(AutoPilotManager)
_stub_manager._current_board = None
Singleton._instances.setdefault(AutoPilotManager, _stub_manager)

from api.v1.routers import index  # noqa: E402 pylint: disable=wrong-import-position
from api.v2.routers import (  # noqa: E402 pylint: disable=wrong-import-position
    index as index_v2,
)

pytestmark = pytest.mark.asyncio

CUBE_BL = FlightController(
    name="CubeOrange-BL",
    manufacturer="CubePilot",
    platform=Platform(name="CubeOrange", platform_type=PlatformType.Serial),
    ardupilot_board_id=140,
    path="/dev/ttyACM0",
    flags=[FlightControllerFlags.is_bootloader],
)
MATEK = FlightController(
    name="MatekH743",
    manufacturer="ArduPilot",
    platform=Platform(name="MatekH743", platform_type=PlatformType.Serial),
    ardupilot_board_id=1013,
    path="/dev/ttyACM1",
)


async def get_v1_board(monkeypatch: pytest.MonkeyPatch, board: Optional[FlightController]) -> Any:
    monkeypatch.setattr(index, "autopilot", SimpleNamespace(current_board=board))
    route = next(route for route in index.index_router_v1.routes if getattr(route, "path", None) == "/board")
    adapter: TypeAdapter[Any] = TypeAdapter(route.response_model)  # type: ignore[attr-defined]
    return adapter.dump_python(adapter.validate_python(await index.get_board()), mode="json")


async def test_v1_board_keeps_old_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    assert await get_v1_board(monkeypatch, CUBE_BL) == {
        "name": "CubeOrange-BL",
        "manufacturer": "CubePilot",
        "platform": "CubeOrange",
        "ardupilot_board_id": 140,
        "path": "/dev/ttyACM0",
        "flags": ["is_bootloader"],
    }


async def test_v1_board_without_running_board(monkeypatch: pytest.MonkeyPatch) -> None:
    assert await get_v1_board(monkeypatch, None) is None


@pytest.mark.parametrize(
    "platform, legacy_name",
    [
        (Platform(name="Navigator", platform_type=PlatformType.Linux), "navigator"),
        (Platform(name="Navigator64", platform_type=PlatformType.Linux), "navigator64"),
        (Platform(name="Argonot", platform_type=PlatformType.Linux), "argonot"),
        (Platform(name="Manual", platform_type=PlatformType.Manual), "Manual"),
        (Platform.SITL(), Platform.SITL().name),
        (Platform(name="Pixhawk1", platform_type=PlatformType.Serial), "Pixhawk1"),
        (Platform(name="Pixhawk4", platform_type=PlatformType.Serial), "Pixhawk4"),
        (Platform(name="Pixhawk6X", platform_type=PlatformType.Serial), "Pixhawk6X"),
        (Platform(name="Pixhawk6C", platform_type=PlatformType.Serial), "Pixhawk6C"),
        (Platform(name="CubeOrange", platform_type=PlatformType.Serial), "CubeOrange"),
        (Platform(name="GenericSerial", platform_type=PlatformType.Serial), "GenericSerial"),
        (Platform(name="MatekH743", platform_type=PlatformType.Serial), "GenericSerial"),
        (Platform(name="CubeOrangePlus", platform_type=PlatformType.Serial), "GenericSerial"),
    ],
)
async def test_v1_board_uses_legacy_platform_names(
    monkeypatch: pytest.MonkeyPatch, platform: Platform, legacy_name: str
) -> None:
    board = FlightController(name="Board", platform=platform)
    assert (await get_v1_board(monkeypatch, board))["platform"] == legacy_name


async def test_target_board_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    available_boards = AsyncMock(return_value=[CUBE_BL, MATEK])
    monkeypatch.setattr(index, "autopilot", SimpleNamespace(current_board=MATEK, available_boards=available_boards))

    assert await index.target_board(None) == MATEK
    available_boards.assert_not_awaited()
    assert await index.target_board(None, 140) == CUBE_BL
    assert await index.target_board("matekh743") == MATEK
    assert await index.target_board("CubeOrange-BL") == CUBE_BL
    assert await index.target_board("MatekH743", 1013) == MATEK
    with pytest.raises(ValueError):
        await index.target_board("MatekH743", 140)
    with pytest.raises(ValueError):
        await index.target_board(None, 9)


@pytest.fixture(name="fake_autopilot")
def fixture_fake_autopilot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    fake = SimpleNamespace(
        current_board=MATEK,
        settings=SimpleNamespace(firmware_folder=tmp_path),
        available_boards=AsyncMock(return_value=[CUBE_BL, MATEK]),
        firmware_manager=MagicMock(),
        install_firmware_from_url=AsyncMock(),
        install_firmware_from_file=AsyncMock(),
        restore_default_firmware=AsyncMock(),
        change_board=AsyncMock(),
    )
    monkeypatch.setattr(index, "autopilot", fake)
    monkeypatch.setattr(index, "install_jobs", FirmwareInstallJobManager())
    return fake


@pytest.fixture(name="client")
def fixture_client() -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(index.index_router_v1)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def test_v1_available_boards_keep_old_shape(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    response = await client.get("/available_boards")
    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "CubeOrange-BL",
            "manufacturer": "CubePilot",
            "platform": "CubeOrange",
            "ardupilot_board_id": 140,
            "path": "/dev/ttyACM0",
            "flags": ["is_bootloader"],
        },
        {
            "name": "MatekH743",
            "manufacturer": "ArduPilot",
            "platform": "GenericSerial",
            "ardupilot_board_id": 1013,
            "path": "/dev/ttyACM1",
            "flags": [],
        },
    ]
    fake_autopilot.available_boards.assert_awaited_once_with(True)


async def test_v2_available_boards(monkeypatch: pytest.MonkeyPatch, fake_autopilot: SimpleNamespace) -> None:
    monkeypatch.setattr(index_v2, "autopilot", fake_autopilot)
    app = FastAPI()
    app.include_router(index_v2.index_router_v2)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/available_boards")
    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "CubeOrange-BL",
            "manufacturer": "CubePilot",
            "platform": {"name": "CubeOrange", "platform_type": "Serial"},
            "ardupilot_board_id": 140,
            "path": "/dev/ttyACM0",
            "flags": ["is_bootloader"],
        },
        {
            "name": "MatekH743",
            "manufacturer": "ArduPilot",
            "platform": {"name": "MatekH743", "platform_type": "Serial"},
            "ardupilot_board_id": 1013,
            "path": "/dev/ttyACM1",
            "flags": [],
        },
    ]
    fake_autopilot.available_boards.assert_awaited_once_with(True)


def stream_lines(response: httpx.Response) -> List[List[str]]:
    return [[entry["stream"], entry["data"]] for entry in map(json.loads, response.text.splitlines())]


def stub_manager() -> AutoPilotManager:
    manager = AutoPilotManager.__new__(AutoPilotManager)
    manager._lifecycle_lock = asyncio.Lock()
    manager._current_board = None
    manager.should_be_running = False
    manager._settings_manager = MagicMock(settings=SimpleNamespace(preferred_board=None))
    return manager


@pytest.mark.usefixtures("fake_autopilot")
async def test_v1_board_round_trip_for_boards_without_legacy_platform(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    matek = (await client.get("/available_boards")).json()[1]
    assert matek["platform"] == "GenericSerial"

    manager = stub_manager()
    monkeypatch.setattr(manager, "available_boards", AsyncMock(return_value=[MATEK]))
    monkeypatch.setattr(manager, "_kill_ardupilot_locked", AsyncMock())
    monkeypatch.setattr(manager, "_start_ardupilot_locked", AsyncMock())
    monkeypatch.setattr(index, "autopilot", manager)

    response = await client.post("/board", json=matek)
    assert response.status_code == 200, response.text
    assert manager.settings.preferred_board == FlightController.model_validate(matek)


def usb_port(device: str, product: str) -> SimpleNamespace:
    return SimpleNamespace(
        device=device,
        name=device.rsplit("/", 1)[-1],
        vid=0x1209,
        pid=0x5740,
        product=product,
        manufacturer="ArduPilot",
        serial_number="0123456789",
        usb_device_path="/sys/devices/usb1/1-1",
        location="1-1:1.0",
    )


@pytest.mark.parametrize("new_path", ["/dev/ttyACM1", "/dev/ttyACM2"])
async def test_flashing_another_build_of_the_running_board(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, new_path: str
) -> None:
    ports = [usb_port("/dev/ttyACM1", "MatekH743")]
    firmware = tmp_path / "firmware.apj"

    async def get_board_id(_device: str) -> int:
        return 1013

    async def flash(*_args: Any) -> Path:
        ports[:] = [usb_port(new_path, "MatekH743-bdshot")]
        return firmware

    async def kill() -> None:
        manager.should_be_running = False

    Detector.invalidate_caches()
    monkeypatch.setattr(Detector, "_port_identities", {})
    monkeypatch.setattr(Detector, "_last_serial_boards", [])
    monkeypatch.setattr(Detector, "_probing_lock", asyncio.Lock())
    monkeypatch.setattr(detector_module, "comports", lambda: ports)
    monkeypatch.setattr(detector_module, "get_board_id", get_board_id)
    monkeypatch.setattr(detector_module, "is_running_as_root", lambda: False)
    manager = stub_manager()
    manager.firmware_manager = MagicMock(install_firmware_from_url=AsyncMock(side_effect=flash))
    monkeypatch.setattr(manager, "setup", AsyncMock())
    monkeypatch.setattr(manager, "start_mavlink_manager", AsyncMock())
    monkeypatch.setattr(manager, "_kill_ardupilot_locked", kill)
    monkeypatch.setattr(index, "autopilot", manager)
    monkeypatch.setattr(index, "install_jobs", FirmwareInstallJobManager())

    await manager.change_board(MATEK)
    assert manager.current_board is not None and manager.current_board.name == "MatekH743"

    response = await client.post("/install_firmware_from_url", params={"url": "https://fw", "make_default": True})
    assert response.status_code == 200
    lines = stream_lines(response)
    assert lines[-1] == ["control", "done"], lines
    assert not [line for line in lines if line[0] == "stderr"]

    bdshot = manager.current_board
    assert bdshot is not None
    assert (bdshot.name, bdshot.platform.name, bdshot.path) == ("MatekH743-bdshot", "MatekH743-bdshot", new_path)
    assert manager.settings.preferred_board == bdshot
    manager.firmware_manager.save_default_firmware.assert_called_once_with(firmware, bdshot.platform)
    Detector.invalidate_caches()


async def test_switching_to_a_renamed_board_after_flashing(
    client: httpx.AsyncClient, fake_autopilot: SimpleNamespace
) -> None:
    bdshot = MATEK.model_copy(
        update={
            "name": "MatekH743-bdshot",
            "platform": Platform(name="MatekH743-bdshot", platform_type=PlatformType.Serial),
        }
    )
    fake_autopilot.current_board = FlightController(name="SITL", platform=Platform.SITL())
    fake_autopilot.available_boards = AsyncMock(return_value=[MATEK])

    async def flash(*_args: Any, **_kwargs: Any) -> None:
        fake_autopilot.available_boards.return_value = [bdshot]

    fake_autopilot.install_firmware_from_url.side_effect = flash

    response = await client.post("/install_firmware_from_url", params={"url": "https://fw", "board_name": "MatekH743"})
    assert response.status_code == 200
    lines = stream_lines(response)
    assert lines[-1] == ["control", "done"], lines
    fake_autopilot.change_board.assert_awaited_once_with(bdshot)


async def test_install_from_url_unknown_board(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    response = await client.post("/install_firmware_from_url", params={"url": "https://fw", "board_name": "Nope"})
    assert response.status_code == 404
    fake_autopilot.install_firmware_from_url.assert_not_awaited()


async def test_install_from_file_invalid_firmware(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    fake_autopilot.firmware_manager.validate_firmware.side_effect = InvalidFirmwareFile("Expected board_id 1013")
    response = await client.post(
        "/install_firmware_from_file", params={"board_name": "MatekH743"}, files={"binary": ("fw.apj", b"{}")}
    )
    assert response.status_code == 415
    assert not (fake_autopilot.settings.firmware_folder / "custom_firmware").exists()
    fake_autopilot.install_firmware_from_file.assert_not_awaited()


async def test_restore_without_default_firmware(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    fake_autopilot.firmware_manager.is_default_firmware_available.return_value = False
    response = await client.post("/restore_default_firmware", params={"board_name": "MatekH743"})
    assert response.status_code == 404
    fake_autopilot.restore_default_firmware.assert_not_awaited()


async def test_install_routes_are_locked_while_busy(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    with index.install_jobs.reserve():
        responses = [
            await client.post("/install_firmware_from_url", params={"url": "https://fw"}),
            await client.post("/install_firmware_from_file", files={"binary": ("fw.apj", b"{}")}),
            await client.post("/restore_default_firmware"),
        ]
    assert [response.status_code for response in responses] == [423, 423, 423]
    assert not (fake_autopilot.settings.firmware_folder / "custom_firmware").exists()


async def test_progress_without_running_install(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    assert (await client.get("/install_firmware_progress")).status_code == 404
    fake_autopilot.restore_default_firmware.assert_not_awaited()


async def test_install_from_file_streams_job(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    custom_firmware = fake_autopilot.settings.firmware_folder / "custom_firmware"

    async def install(firmware: Path, *_args: Any, output_callback: OutputCallback) -> None:
        assert firmware.read_bytes() == b"{}"
        await output_callback("stdout", "flashing")

    fake_autopilot.install_firmware_from_file.side_effect = install
    response = await client.post(
        "/install_firmware_from_file", params={"board_name": "MatekH743"}, files={"binary": ("fw.apj", b"{}")}
    )
    assert response.status_code == 200
    assert stream_lines(response) == [
        ["stdout", "Stopping autopilot"],
        ["stdout", "flashing"],
        ["stdout", "Autopilot restarted"],
        ["stdout", "Cleaned up temporary firmware file"],
        ["control", "done"],
    ]
    assert not custom_firmware.exists()


async def test_progress_replays_running_install(client: httpx.AsyncClient, fake_autopilot: SimpleNamespace) -> None:
    release = asyncio.Event()

    async def restore(*_args: Any, output_callback: OutputCallback) -> None:
        await output_callback("stdout", "flashing")
        await release.wait()

    fake_autopilot.restore_default_firmware.side_effect = restore
    install = asyncio.create_task(client.post("/restore_default_firmware", params={"board_name": "MatekH743"}))
    while index.install_jobs.running_job is None:
        await asyncio.sleep(0.01)
    progress = asyncio.create_task(client.get("/install_firmware_progress"))
    await asyncio.sleep(0.05)
    release.set()

    install_response, progress_response = await install, await progress
    assert progress_response.status_code == 200
    assert stream_lines(progress_response) == stream_lines(install_response)
    assert stream_lines(progress_response)[:2] == [["stdout", "Stopping autopilot"], ["stdout", "flashing"]]
    assert stream_lines(progress_response)[-1] == ["control", "done"]
    assert (await client.get("/install_firmware_progress")).status_code == 404
