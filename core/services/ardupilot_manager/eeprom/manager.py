import asyncio
import json
import os
from enum import IntEnum

import aiohttp
from commonwealth.mavlink_comm.exceptions import MavlinkMessageReceiveFail
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger

from .calibration import CALIBRATION_PARAM, CalibrationDB
from .device import EEPROM


class Status(IntEnum):
    EEPROM_NOT_FOUND = 0
    READ_ONLY = 1
    VALID = 2


class EEPROMManager:
    EEPROM_PATH = os.environ.get("BLUEOS_EEPROM_PATH", "/sys/bus/i2c/devices/0-0050/eeprom")

    def __init__(self) -> None:
        self.eeprom = EEPROM(self.EEPROM_PATH)
        self.mavlink = MavlinkMessenger()

    def status(self) -> Status:
        if not os.path.exists(self.EEPROM_PATH):
            return Status.EEPROM_NOT_FOUND
        if not os.access(self.EEPROM_PATH, os.W_OK):
            return Status.READ_ONLY
        return Status.VALID

    async def mavlink_online(self) -> bool:
        try:
            await self.mavlink.get_mavlink_message("HEARTBEAT")
        except (aiohttp.ClientError, MavlinkMessageReceiveFail):
            return False
        return True

    def read_calibration(self) -> CalibrationDB | None:
        return CalibrationDB.find(self.eeprom.read(0, self.eeprom.size()))

    def dump(self) -> bytes:
        return self.eeprom.read(0, self.eeprom.size())

    async def fetch_params(self, timeout: float = 10.0) -> dict[str, float]:
        params: dict[str, float] = {}
        received: set[int] = set()
        if not await self.mavlink_online():
            raise RuntimeError("MAVLink is not available")
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"http://{self.mavlink.m2r_address}/ws/mavlink?filter=PARAM_VALUE") as ws:
                await self.mavlink.send_mavlink_message(
                    {"type": "PARAM_REQUEST_LIST", "target_system": self.mavlink.system_id, "target_component": 1}
                )
                try:
                    async with asyncio.timeout(timeout):
                        async for msg in ws:
                            message = json.loads(msg.data)["message"]
                            name = "".join(message["param_id"]).rstrip("\0")
                            if CALIBRATION_PARAM.match(name):
                                params[name] = message["param_value"]
                            received.add(message["param_index"])
                            if len(received) == message["param_count"]:
                                break
                except TimeoutError:
                    # Some parameters may not be available
                    pass
        return params

    async def backup(self) -> dict[str, float]:
        if not await self.mavlink_online():
            raise RuntimeError("MAVLink is not available")
        params = await self.fetch_params()
        if not params:
            raise RuntimeError("No parameters received from the autopilot")
        existing = self.read_calibration()
        # Override the existing backup, otherwise create it after the hat id partition
        offset = self.eeprom.hat_id_partition_size()
        if existing and existing.offset is not None:
            offset = existing.offset
        calibration = CalibrationDB.from_params(params)
        self.eeprom.write(offset, calibration.to_bytes())
        return calibration.to_params()
