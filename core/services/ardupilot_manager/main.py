#! /usr/bin/env python3
import os
import stat
import subprocess
import time
from typing import Any, List, Optional, Tuple

import appdirs
from firmware_download.FirmwareDownload import FirmwareDownload, Vehicle
from flight_controller_detector.Detector import Detector as BoardDetector
from flight_controller_detector.Detector import FlightControllerType
from mavlink_proxy.Endpoint import Endpoint
from mavlink_proxy.Manager import Manager as MavlinkManager


class ArduPilotManager:
    def __init__(self) -> None:
        self.mavlink_manager = MavlinkManager()
        available_mavlink_interfaces = self.mavlink_manager.available_interfaces()
        if not available_mavlink_interfaces:
            raise RuntimeError("No MAVLink interface available.")

        # Create a folder for ArduPilotManager service
        self.settings_path = appdirs.user_config_dir(self.__class__.__name__)
        self.firmware_path = os.path.join(self.settings_path, "firmware")
        self.subprocess: Optional[Any] = None
        self.firmware_download = FirmwareDownload()

        # Create settings folder, ignore if already exists
        os.makedirs(self.firmware_path, exist_ok=True)

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
        firmware = os.path.join(self.firmware_path, "ardusub")
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

        local_endpoint = "tcp:0.0.0.0:5766"
        self.subprocess = subprocess.Popen(
            [
                firmware,
                "-A",
                local_endpoint,
                "--log-directory",
                f"{self.firmware_path}/logs/",
                "--storage-directory",
                f"{self.firmware_path}/storage/",
            ],
            shell=False,
            encoding="utf-8",
            errors="ignore",
        )

        # ArduPilot master is not working with UDP endpoints and mavlink-router
        # does not accept TCP master endpoints
        # self.start_mavlink_manager(Endpoint(local_endpoint))

    def start_serial(self, device: str) -> None:
        self.start_mavlink_manager(Endpoint(f"serial:{device}:115200"))

    def start_mavlink_manager(self, device: Endpoint) -> None:
        self.mavlink_manager.add_endpoints([Endpoint("udpin:0.0.0.0:14550")])
        self.mavlink_manager.set_master_endpoint(device)
        self.mavlink_manager.start()
        while self.mavlink_manager.is_running():
            time.sleep(1)

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
        elif FlightControllerType.Serial == flight_controller_type:
            self.start_serial(place)
        else:
            raise RuntimeError("Invalid board type: {boards}")

        return False


if __name__ == "__main__":
    ardupilot_manager = ArduPilotManager()
    ardupilot_manager.run()
