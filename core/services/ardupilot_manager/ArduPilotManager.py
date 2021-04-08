import os
import stat
import subprocess
import time
from copy import deepcopy
from pprint import pprint
from typing import Any, List, Optional, Tuple
from warnings import warn

from firmware_download.FirmwareDownload import FirmwareDownload, Vehicle
from flight_controller_detector.Detector import Detector as BoardDetector
from flight_controller_detector.Detector import FlightControllerType
from mavlink_proxy.Endpoint import Endpoint, EndpointType
from mavlink_proxy.Manager import Manager as MavlinkManager
from settings import Settings
from Singleton import Singleton


class ArduPilotManager(metaclass=Singleton):
    def __init__(self) -> None:
        self.settings = Settings()
        self.mavlink_manager = MavlinkManager()

        # Load settings and do the initial configuration
        if self.settings.load():
            print(f"Loaded settings from {self.settings.settings_file}:")
            pprint(self.settings.content)
        else:
            self.settings.create_settings()

        self.configuration = deepcopy(self.settings.content)
        self._load_endpoints()
        self.subprocess: Optional[Any] = None
        self.firmware_download = FirmwareDownload()

    def run(self) -> None:
        ArduPilotManager.check_running_as_root()

        while not self.start_board(BoardDetector.detect()):
            print("Flight controller board not detected, will try again.")
            time.sleep(2)

    @staticmethod
    def check_running_as_root() -> None:
        if os.geteuid() != 0:
            raise RuntimeError("ArduPilot manager needs to run with root privilege.")

    def start_navigator(self) -> None:
        firmware = os.path.join(self.settings.firmware_path, "ardusub")
        if not os.path.isfile(firmware):
            temporary_file = self.firmware_download.download(Vehicle.Sub, "Navigator")
            assert temporary_file, "Failed to download navigator binary."
            # Make the binary executable
            os.chmod(temporary_file, stat.S_IXOTH)
            os.rename(temporary_file, firmware)
        try:
            subprocess.check_output([firmware, "--help"])
        except Exception as error:
            raise RuntimeError(f"Failed to start navigator: {error}") from error

        local_endpoint = "tcp:0.0.0.0:5760"
        self.subprocess = subprocess.Popen(
            [
                firmware,
                "-A",
                local_endpoint,
                "--log-directory",
                f"{self.settings.firmware_path}/logs/",
                "--storage-directory",
                f"{self.settings.firmware_path}/storage/",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )

        # TODO: Fix ArduPilot UDP communication to use mavlink_manager
        # ArduPilot master is not working with UDP endpoints and mavlink-router
        # does not accept TCP master endpoints
        # self.start_mavlink_manager(Endpoint(local_endpoint))

    def start_serial(self, device: str) -> None:
        self.start_mavlink_manager(Endpoint("serial", device, 115200))

    def start_mavlink_manager(self, device: Endpoint) -> None:
        self.add_new_endpoints([Endpoint("udpin", "0.0.0.0", 14550)])
        self.mavlink_manager.set_master_endpoint(device)
        self.mavlink_manager.start()

    def start_board(self, boards: List[Tuple[FlightControllerType, str]]) -> bool:
        if not boards:
            return False

        if len(boards) > 1:
            print(f"More than a single board detected: {boards}")

        # Sort by priority
        boards.sort(key=lambda tup: tup[0].value)

        flight_controller_type, place = boards[0]

        if FlightControllerType.Navigator == flight_controller_type:
            self.start_navigator()
            return True
        if FlightControllerType.Serial == flight_controller_type:
            self.start_serial(place)
            return True
        raise RuntimeError("Invalid board type: {boards}")

    def restart(self) -> bool:
        return self.mavlink_manager.restart()

    def _load_endpoints(self) -> None:
        """Load endpoints from the configuration file to the mavlink manager."""
        if "endpoints" not in self.configuration:
            self.configuration["endpoints"] = []
        endpoints = self.configuration["endpoints"]
        for endpoint in endpoints:
            if not self.mavlink_manager.add_endpoint(Endpoint(**endpoint)):
                warn(f"Could not load endpoint {endpoint}")

    def _reset_endpoints(self, endpoints: List[Endpoint]) -> None:
        try:
            self.mavlink_manager.clear_endpoints()
            self.mavlink_manager.add_endpoints(endpoints)
            print("Reseting endpoints to previous state.")
        except Exception as error:
            warn(f"Error reseting endpoints: {error}")

    def _update_endpoints(self, updated_endpoints: List[Endpoint]) -> bool:
        try:
            self.configuration["endpoints"] = deepcopy(updated_endpoints)
            self.settings.save(self.configuration)
            return self.restart()
        except Exception as error:
            warn(f"Error updating endpoints: {error}")
            return False

    def get_endpoints(self) -> List[Endpoint]:
        """Get all endpoints from the mavlink manager."""
        return self.mavlink_manager.endpoints()

    def add_new_endpoints(self, new_endpoints: List[Endpoint]) -> bool:
        """Add multiple endpoints to the mavlink manager and save them on the configuration file."""
        for endpoint in new_endpoints:
            if endpoint.connection_type == EndpointType.File.value:
                endpoint.place = os.path.join(self.settings.file_endpoints_path, endpoint.place)

        saved_endpoints = deepcopy(self.configuration["endpoints"])
        loaded_endpoints = deepcopy(self.get_endpoints())

        for endpoint in new_endpoints:
            if endpoint.asdict() in saved_endpoints:
                warn(f"Endpoint {endpoint} already stored.")
                self._reset_endpoints(loaded_endpoints)
                return False
            if not self.mavlink_manager.add_endpoint(endpoint):
                warn(f"Mavlink manager failed to add endpoint {endpoint}.")
                self._reset_endpoints(loaded_endpoints)
                return False
            saved_endpoints.append(endpoint.asdict())
            print(f"Adding endpoint {endpoint} and saving it to the settings file.")

        return self._update_endpoints(saved_endpoints)

    def remove_endpoints(self, endpoints_to_remove: List[Endpoint]) -> bool:
        """Remove multiple endpoints from the mavlink manager and save them on the configuration file."""

        saved_endpoints = deepcopy(self.configuration["endpoints"])
        loaded_endpoints = deepcopy(self.get_endpoints())

        for endpoint in endpoints_to_remove:
            if not endpoint.asdict() in saved_endpoints:
                warn(f"Endpoint {endpoint} not found.")
                self._reset_endpoints(loaded_endpoints)
                return False
            if not self.mavlink_manager.remove_endpoint(endpoint):
                warn(f"Mavlink manager failed to remove endpoint {endpoint}.")
                self._reset_endpoints(loaded_endpoints)
                return False
            saved_endpoints.remove(endpoint.asdict())
            print(f"Deleting endpoint {endpoint} and removing it from the settings file.")

        return self._update_endpoints(saved_endpoints)
