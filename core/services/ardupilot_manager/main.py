#! /usr/bin/env python3
import os
import time
from typing import List, Tuple

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

    def run(self) -> None:
        ArduPilotManager.check_running_as_root()

        while not self.start_board(BoardDetector.detect()):
            print("Flight controller board not detected, will try again.")
            time.sleep(2)

    @staticmethod
    def check_running_as_root() -> None:
        if os.geteuid() != 0:
            raise RuntimeError("ArduPilot manager needs to run with root privilege.")

    @staticmethod
    def start_navigator() -> None:
        raise NotImplementedError("We only support ArduPilot running on serial devices.")

    def start_serial(self, device: str) -> None:
        self.mavlink_manager.add_endpoints([Endpoint("udpin:0.0.0.0:14550")])
        self.mavlink_manager.set_master_endpoint(Endpoint(f"serial:{device}:115200"))
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
            ArduPilotManager.start_navigator()
        elif FlightControllerType.Serial == flight_controller_type:
            self.start_serial(place)
        else:
            raise RuntimeError("Invalid board type: {boards}")

        return False


if __name__ == "__main__":
    ardupilot_manager = ArduPilotManager()
    ardupilot_manager.run()
