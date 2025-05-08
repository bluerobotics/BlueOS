import asyncio
import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
from loguru import logger

from commonwealth.mavlink_comm.exceptions import (
    FetchUpdatedMessageFail,
    MavlinkMessageReceiveFail,
    MavlinkMessageSendFail,
)
from commonwealth.mavlink_comm.typedefs import MavlinkVehicleType


class MavlinkMessenger:
    def __init__(self) -> None:
        self.system_id = int(os.environ.get("MAV_SYSTEM_ID", 1))
        self.component_id = int(os.environ.get("MAV_COMPONENT_ID_ONBOARD_COMPUTER4", 194))
        self.sequence = 0
        self.m2r_address = "localhost:6040"

    def set_system_id(self, system_id: int) -> None:
        logger.info(f"system_id set to: {system_id}")
        self.system_id = system_id

    def set_component_id(self, component_id: int) -> None:
        self.component_id = component_id

    def set_sequence(self, sequence: int) -> None:
        self.sequence = sequence

    def set_m2r_address(self, address: str) -> None:
        if len(address.split(":")) != 2:
            raise ValueError("Invalid address. Valid address should follow the format 'localhost:6040'.")
        self.m2r_address = address

    @property
    def m2r_rest_url(self) -> str:
        return f"http://{self.m2r_address}/mavlink"

    async def get_all_mavlink(self) -> Any:
        request_timeout = 1.0
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.m2r_rest_url, timeout=request_timeout) as response:
                    if not response.status == 200:
                        raise MavlinkMessageReceiveFail(f"Received status code of {response.status}.")
                    message = await response.json()
            except asyncio.exceptions.TimeoutError as error:
                raise MavlinkMessageReceiveFail(f"Request timed out after {request_timeout} second.") from error
        return message

    async def get_mavlink_message(
        self, message_name: Optional[str] = None, vehicle: Optional[int] = None, component: Optional[int] = 1
    ) -> Any:
        request_url = f"{self.m2r_rest_url}/vehicles/{vehicle or self.system_id}/components/{component}/messages"
        if message_name:
            request_url += f"/{message_name.upper()}"

        request_timeout = 1.0
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(request_url, timeout=request_timeout) as response:
                    if not response.status == 200:
                        raise MavlinkMessageReceiveFail(f"Received status code of {response.status}.")
                    # if message is "None", try re-detecting systemid
                    if await response.text() == "None":
                        self.set_system_id(await self.get_most_recent_vehicle_id())
                        raise MavlinkMessageReceiveFail("Received empty response")
                    message = await response.json()
            except asyncio.exceptions.TimeoutError as error:
                raise MavlinkMessageReceiveFail(f"Request timed out after {request_timeout} second.") from error

        return message

    async def get_most_recent_vehicle_id(self) -> int:
        json_data = await self.get_all_mavlink()
        most_recent_timestamp = datetime.min
        most_recent_vehicle_id = None
        for vehicle_id, vehicle in json_data["vehicles"].items():

            for component in vehicle["components"].values():
                if "HEARTBEAT" in component["messages"]:
                    message = component["messages"]["HEARTBEAT"]
                    # we are looking for vehicles, not GCSs or other components
                    if not MavlinkVehicleType[message["message"]["mavtype"]["type"]].is_actually_a_vehicle():
                        continue
                    last_update_str = message["status"]["time"]["last_update"]
                    # drop sub-microsecond precision as it is not supported by datetime.fromisoformat
                    last_update_str = re.sub(r"(\.\d{6})\d+Z?", r"\1", last_update_str)
                    last_update = datetime.fromisoformat(last_update_str)

                    if last_update > most_recent_timestamp:
                        most_recent_timestamp = last_update
                        most_recent_vehicle_id = vehicle_id
        if most_recent_vehicle_id:
            logger.debug(f"{most_recent_vehicle_id} (detected)")
            return int(most_recent_vehicle_id)
        logger.debug("no vehicle ID detected - using default (1)")
        return 1

    async def get_updated_mavlink_message(
        self,
        message_name: str,
        vehicle: Optional[int] = None,
        component: int = 1,
        timeout: float = 10.0,
    ) -> Any:
        first_message = await self.get_mavlink_message(message_name, vehicle or self.system_id, component)
        first_message_counter = first_message["status"]["time"]["counter"]
        t0 = time.time()
        while True:
            new_message = await self.get_mavlink_message(message_name, vehicle or self.system_id, component)
            new_message_counter = new_message["status"]["time"]["counter"]
            if new_message_counter > first_message_counter:
                break
            if (time.time() - t0) > timeout / 2:
                logger.warning(f"no new messages after {timeout/2} seconds, triggering system-id detection")
                self.set_system_id(await self.get_most_recent_vehicle_id())
                raise FetchUpdatedMessageFail(f"Did not receive an updated {message_name} before timeout.")
            await asyncio.sleep(timeout / 10.0)

        return new_message

    async def send_mavlink_message(self, message: Dict[str, Any]) -> None:
        mavlink2rest_package = {
            "header": {"system_id": self.system_id, "component_id": self.component_id, "sequence": self.sequence},
            "message": message,
        }

        request_timeout = 1.0
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.m2r_rest_url, data=json.dumps(mavlink2rest_package), timeout=request_timeout
                ) as response:
                    if not response.status == 200:
                        logger.warning(await response.text())
                        raise MavlinkMessageSendFail(f"Received status code of {response.status}.")
            except asyncio.exceptions.TimeoutError as error:
                raise MavlinkMessageSendFail(f"Request timed out after {request_timeout} second.") from error
