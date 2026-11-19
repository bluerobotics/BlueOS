import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, AsyncIterator, List, Optional

import aiohttp
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration.job import Heard, LinkLost
from clients.mavlink import (
    AUTOPILOT_COMPONENT_ID,
    MESSAGE_FILTER,
    autopilot_message,
    read,
)
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger

ACK = {
    "type": "COMMAND_ACK",
    "command": {"type": "MAV_CMD_PREFLIGHT_CALIBRATION"},
    "result": {"type": "MAV_RESULT_ACCEPTED"},
}


def frame(system_id: Any, component_id: Any, message: Any) -> str:
    return json.dumps({"header": {"system_id": system_id, "component_id": component_id}, "message": message})


def test_keeps_the_autopilots_messages() -> None:
    assert autopilot_message(frame(7, 1, ACK), 7) == ACK


@pytest.mark.parametrize(
    "text",
    [
        frame(1, 1, ACK),
        frame(7, 194, {"type": "COMMAND_LONG"}),
        frame(7, 1, {"type": "HEARTBEAT"}),
        frame(7, 1, "COMMAND_ACK"),
        json.dumps({"message": ACK}),
        json.dumps([ACK]),
        "{'header': ",
    ],
)
def test_drops_everything_else(text: str) -> None:
    assert autopilot_message(text, 7) is None


@pytest.mark.parametrize(
    "name, kept",
    [
        ("COMMAND_ACK", True),
        ("MAG_CAL_REPORT", True),
        ("COMMAND_ACK_EXTRA", False),
        ("HEARTBEAT", False),
    ],
)
def test_the_websocket_filter_matches_whole_names(name: str, kept: bool) -> None:
    assert bool(re.search(MESSAGE_FILTER, name)) == kept


async def websocket(
    frames: List[aiohttp.WSMessage], error: Optional[Exception] = None
) -> AsyncIterator[aiohttp.WSMessage]:
    for item in frames:
        yield item
    if error is not None:
        raise error


def text_frame(data: str) -> aiohttp.WSMessage:
    return aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, data, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error, reason",
    [
        (None, "mavlink2rest's websocket closed"),
        (aiohttp.ClientError("reset"), "mavlink2rest's websocket failed: reset"),
    ],
)
async def test_a_dropped_websocket_delivers_link_lost(error: Optional[Exception], reason: str) -> None:
    delivered: List[Any] = []
    frames = [
        text_frame(frame(7, 1, ACK)),
        aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"", None),
        text_frame(frame(7, 194, ACK)),
    ]
    await read(websocket(frames, error), 7, delivered.append)
    assert delivered == [Heard(ACK), LinkLost(reason)]


@pytest.mark.asyncio
async def test_a_cancelled_reader_delivers_nothing() -> None:
    delivered: List[Any] = []
    never: "asyncio.Future[None]" = asyncio.get_running_loop().create_future()

    async def silent() -> AsyncIterator[aiohttp.WSMessage]:
        await never
        yield text_frame(frame(7, 1, ACK))

    reader = asyncio.create_task(read(silent(), 7, delivered.append))
    await asyncio.sleep(0)
    reader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await reader
    assert not delivered


def test_our_header_is_never_the_autopilots() -> None:
    # Otherwise our own COMMAND_LONGs would pass as the autopilot's
    assert MavlinkMessenger().component_id != AUTOPILOT_COMPONENT_ID
