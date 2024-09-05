from copy import deepcopy
from typing import Optional

from loguru import logger

from autopilot.platform import AutopilotPlatform
from autopilot.firmware import AutopilotFirmware
from controller.controller import FlightController
from settings import Settings
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.Manager import Manager as MavlinkManager


class AutopilotManager:
    def __init__(self) -> None:
        self.controller: Optional[FlightController] = None
        self.platform: Optional[AutopilotPlatform] = None
        self.firmware: Optional[AutopilotFirmware] = None

        self.settings = Settings()
        self.settings.create_app_folders()

        # Load settings and do the initial configuration
        if self.settings.load():
            logger.info(f"Loaded settings from {self.settings.settings_file}.")
            logger.debug(self.settings.content)
        else:
            self.settings.create_settings_file()

    async def setup(self) -> None:
        # This is the logical continuation of __init__(), extracted due to its async nature
        self.configuration = deepcopy(self.settings.content)
        self.mavlink_manager = MavlinkManager(self.load_preferred_router())
        if not self.load_preferred_router():
            await self.set_preferred_router(self.mavlink_manager.available_interfaces()[0].name())
            logger.info(f"Setting {self.mavlink_manager.available_interfaces()[0].name()} as preferred router.")
        self.mavlink_manager.set_logdir(self.settings.log_path)

        self._load_endpoints()
        self.ardupilot_subprocess: Optional[Any] = None

        self.firmware_manager = FirmwareManager(
            self.settings.firmware_folder, self.settings.defaults_folder, self.settings.user_firmware_folder
        )
        self.vehicle_manager = VehicleManager()

        self.should_be_running = False
        self.remove_old_logs()
        self.current_sitl_frame = self.load_sitl_frame()
