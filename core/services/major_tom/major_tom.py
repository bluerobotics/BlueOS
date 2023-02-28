import asyncio
from typing import Any, Dict, List

import requests
from commonwealth.settings.manager import Manager
from loguru import logger

from session_tracker import SessionTracker
from settings import SettingsV1
from system_data import SystemDataGatherer

SERVICE_NAME = "major_tom"
TELEMETRY_VERSION = 1


class MajorTom:
    """
    Consolidates data from SessionTracker and SystenDataGatherer in one place and sends it to GroundControl
    """

    last_session = Dict[str, Any]

    def __init__(self) -> None:
        self.system_data_gatherer = SystemDataGatherer()
        self.settings_manager = Manager(SERVICE_NAME, SettingsV1)
        self.sessions_folder = self.settings_manager.config_folder / "sessions"
        self.sessions_folder.mkdir(parents=True, exist_ok=True)
        self.session_tracker = SessionTracker(self.sessions_folder)
        self.settings = self.settings_manager.settings
        self.remote = self.settings.remote

    def phone_home(self, vehicle_data: Dict[str, Any], system_data: Dict[str, Any]) -> int:
        """
        Sends data to GroundControl
        """
        blacklist = self.settings_manager.settings.blacklist
        filtered_vehicle_data = {key: value for key, value in vehicle_data.items() if key not in blacklist}
        filtered_system_data = {key: value for key, value in system_data.items() if key not in blacklist}
        try:
            req = requests.post(
                f"{self.remote}/v1.0/telemetry/send",
                json={
                    "version": TELEMETRY_VERSION,
                    "vehicle_data": filtered_vehicle_data,
                    "system_data": filtered_system_data,
                },
                timeout=5,
            )
        except Exception as e:
            logger.debug(f"Failed to phone home: {e}")
            return 523  # 523: Origin Unreachable
        return req.status_code

    def get_blacklist(self) -> Any:
        return self.settings_manager.settings.blacklist

    def set_blacklist(self, blacklist: List[str]) -> List[str]:
        self.settings_manager.settings.blacklist = blacklist
        self.settings_manager.save()
        return self.settings_manager.settings.blacklist

    def get_remote(self) -> Any:
        return self.settings_manager.settings.blacklist

    def set_remote(self, remote: str) -> List[str]:
        self.settings_manager.settings.remote = remote
        self.settings_manager.save()
        return self.settings_manager.settings.remote

    async def run(self) -> None:
        while True:
            try:
                await self.session_tracker.update_session()
            except Exception as e:
                logger.warning(f"Failed to update flight session stats: {e}")
                # walrus?
            last_session = self.session_tracker.get_oldest_session()
            system_data = self.system_data_gatherer.get_system_data()
            if self.phone_home(vehicle_data=last_session, system_data=system_data) == 200:
                self.session_tracker.delete_oldest_session()

            await asyncio.sleep(10)
