from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest
from autopilot_manager import AutoPilotManager
from commonwealth.utils.Singleton import Singleton
from pydantic import TypeAdapter
from typedefs import FlightController, FlightControllerFlags, Platform, PlatformType

# Importing the routers instantiates the AutoPilotManager singleton, which touches the real settings and folders
_stub_manager = AutoPilotManager.__new__(AutoPilotManager)
_stub_manager._current_board = None
Singleton._instances.setdefault(AutoPilotManager, _stub_manager)

from api.v1.routers import index  # noqa: E402 pylint: disable=wrong-import-position

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
