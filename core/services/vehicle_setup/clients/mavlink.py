import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from typing import Any, AsyncIterable, AsyncIterator, Callable, Dict, Optional

import aiohttp
from calibration.job import Connect, Connected, Heard, LinkLost, Send
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from job_list.job import Io
from loguru import logger

# Our own header comes from commonwealth's MavlinkMessenger, (MAV_SYSTEM_ID, 194); it must differ from the autopilot's
SYSTEM_ID = int(os.environ.get("MAV_SYSTEM_ID", 1))
AUTOPILOT_COMPONENT_ID = 1

MAVLINK2REST_WEBSOCKET = "http://localhost:6040/ws/mavlink"
AUTOPILOT_MESSAGES = ("COMMAND_ACK", "COMMAND_LONG", "MAG_CAL_PROGRESS", "MAG_CAL_REPORT")
# mavlink2rest matches this regex against each message name, unanchored
MESSAGE_FILTER = f"^({'|'.join(AUTOPILOT_MESSAGES)})$"


def autopilot_message(text: str, system_id: int) -> Optional[Dict[str, Any]]:
    try:
        content = json.loads(text)
    except ValueError:
        return None
    if not isinstance(content, dict) or not isinstance(content.get("header"), dict):
        return None
    header, message = content["header"], content.get("message")
    if (header.get("system_id"), header.get("component_id")) != (system_id, AUTOPILOT_COMPONENT_ID):
        return None
    if not isinstance(message, dict) or message.get("type") not in AUTOPILOT_MESSAGES:
        return None
    return message


async def is_armed() -> bool:
    vehicle = VehicleManager()
    vehicle.mavlink2rest.set_system_id(await autopilot_system_id(vehicle))
    return await vehicle.is_vehicle_armed()


async def autopilot_system_id(vehicle: VehicleManager) -> int:
    try:
        return await vehicle.mavlink2rest.get_most_recent_vehicle_id()
    except Exception as error:
        logger.warning(f"Could not read the autopilot's system id, using {SYSTEM_ID}: {error}")
        return SYSTEM_ID


# Cancelled when the link closes, so only a drop while the job runs reaches LinkLost
async def read(websocket: AsyncIterable[aiohttp.WSMessage], system_id: int, deliver: Callable[[Any], None]) -> None:
    try:
        async for frame in websocket:
            if frame.type == aiohttp.WSMsgType.TEXT:
                message = autopilot_message(frame.data, system_id)
                if message is not None:
                    deliver(Heard(message))
        reason = "mavlink2rest's websocket closed"
    except Exception as error:
        reason = f"mavlink2rest's websocket failed: {error}"
    # No reconnect: the messages missed meanwhile can't be replayed, so a drop fails the job
    logger.warning(reason)
    deliver(LinkLost(reason))


@asynccontextmanager
async def autopilot_link(deliver: Callable[[Any], None]) -> AsyncIterator[Io]:
    vehicle = VehicleManager()
    vehicle.set_target_component(AUTOPILOT_COMPONENT_ID)
    reader: Optional["asyncio.Task[None]"] = None
    websocket: Optional[aiohttp.ClientWebSocketResponse] = None
    async with aiohttp.ClientSession() as session:

        async def run(request: Any) -> Any:
            nonlocal reader, websocket
            if isinstance(request, Connect):
                system_id = await autopilot_system_id(vehicle)
                vehicle.set_target_system(system_id)
                websocket = await session.ws_connect(MAVLINK2REST_WEBSOCKET, params={"filter": MESSAGE_FILTER})
                reader = asyncio.create_task(read(websocket, system_id, deliver))
                return Connected()
            if isinstance(request, Send):
                message = vehicle.command_long_message(request.command.command, request.command.params)
                await vehicle.mavlink2rest.send_mavlink_message(message)
                return None
            raise ValueError(f"unknown request {request}")

        try:
            yield run
        finally:
            if reader is not None:
                reader.cancel()
                with suppress(asyncio.CancelledError):
                    await reader
            if websocket is not None:
                await websocket.close()
