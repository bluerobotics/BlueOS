import asyncio
import glob
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
from commonwealth.mavlink_comm.MavlinkComm import MavlinkMessenger
from commonwealth.mavlink_comm.typedefs import MavlinkVehicleType
from commonwealth.mavlink_comm.VehicleManager import VehicleManager
from loguru import logger


@dataclass
class SessionRegistry:
    # pylint: disable=too-many-instance-attributes
    session_time: float
    session_start: float
    maximum_depth: float
    used_modes: List[int]
    minimum_temperature: float
    maximum_temperature: float
    maximum_battery_voltage: float
    vehicle_type: MavlinkVehicleType


class SessionTracker:
    # pylint: disable=too-many-instance-attributes
    """
    periodically talks to mavlink2rest to check the vehicle status, and saves information
    for each "session" (consisting of an Armed period) into a succint text file.
    """

    session_time: float  # session time in seconds
    session_start: float  # time.time() object of when the session started
    # should we worry about time changes from the topside in here?
    start_location: Dict[str, float]  # GPS coordinates of where the session started

    maximum_depth: float = 0  # maximum depth achieved in meters
    modes: Set[int]  # list of MAVLINK's base_mode entries
    session_in_progress: bool = False

    minimum_temperature: float = 100
    maximum_temperature: float = 0

    maximum_cpu_temperature: float = 0

    maximum_voltage: float = 0

    should_run: bool = True

    oldest_session: Optional[Path] = None

    # TODO: maximum_angle: float # either roll or pitch, we don't care

    def __init__(self, sessions_folder: Path) -> None:
        self.mavlink2rest = MavlinkMessenger()
        self.vehicle_manager = VehicleManager()
        self.modes = set()
        self.sessions_folder = sessions_folder
        self.start_location = {}

    def start_new_session(self) -> None:
        self.session_time = 0
        self.session_start = time.time()
        print("started new session")

    async def update_session(self) -> None:
        vehicle_type = await self.vehicle_manager.get_vehicle_type()
        # armed
        armed = await self.vehicle_manager.is_vehicle_armed()
        # flight modes
        mode = await self.vehicle_manager.get_vehicle_base_mode()
        # depth
        self.modes.add(mode)
        depth = -(await self.mavlink2rest.get_updated_mavlink_message("AHRS2"))["message"]["altitude"]
        self.maximum_depth = max(self.maximum_depth, depth)
        # temperature
        water_temperature = (await self.mavlink2rest.get_updated_mavlink_message("SCALED_PRESSURE2"))["message"][
            "temperature"
        ] / 100

        self.minimum_temperature = min(self.minimum_temperature, water_temperature)
        self.maximum_temperature = max(self.maximum_temperature, water_temperature)
        self.maximum_cpu_temperature = requests.get("http://localhost:6030/system/temperature", timeout=2).json()[0][
            "maximum_temperature"
        ]

        self.maximum_voltage = (await self.mavlink2rest.get_updated_mavlink_message("BATTERY_STATUS"))["message"][
            "voltages"
        ][0] / 100

        # if gps is not set, try to set it
        if len(self.start_location.keys()) == 0:
            try:
                self.start_location = {
                    "lat": (await self.mavlink2rest.get_updated_mavlink_message("GPS_RAW_INT"))["message"]["lat"] / 1e7,
                    "lon": (await self.mavlink2rest.get_updated_mavlink_message("GPS_RAW_INT"))["message"]["lon"] / 1e7,
                }
            except Exception as e:
                print(f"unable to set start location: {e}")

        if not armed and self.session_in_progress:
            self.session_in_progress = False
            self.write_session(
                SessionRegistry(
                    session_time=time.time() - self.session_start,
                    session_start=self.session_start,
                    maximum_depth=self.maximum_depth,
                    used_modes=list(self.modes),
                    minimum_temperature=self.minimum_temperature,
                    maximum_temperature=self.maximum_temperature,
                    maximum_battery_voltage=self.maximum_voltage,
                    vehicle_type=vehicle_type,
                )
            )
        elif armed and not self.session_in_progress:
            self.session_in_progress = True
            self.start_new_session()

    def write_session(self, session: SessionRegistry) -> None:
        filename = f"{self.sessions_folder}/registry-{session.session_start}.txt"
        print(f"writing session to file '{filename}'")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(json.dumps(asdict(session)))

    def get_oldest_session(self) -> Dict[Any, Any]:
        try:
            oldest_file = min(glob.glob(f"{self.sessions_folder}/registry-*.txt"), key=os.path.getctime)
            self.oldest_session = oldest_file
            with open(oldest_file, "r", encoding="utf-8") as f:
                content: Dict[Any, Any] = json.loads(f.read())
                return content
        except Exception as e:
            logger.info(f"error getting oldest registry: {e}, are there no sessions registered?")
            return {}

    def delete_oldest_session(self) -> None:
        try:
            if self.oldest_session:
                os.remove(self.oldest_session)
                self.oldest_session = None
        except Exception as e:
            logger.info(f"error deleting oldest registry: {e}, are there no sessions registered?")

    async def run(self) -> None:
        while self.should_run:
            await self.update_session()
            await asyncio.sleep(5)
