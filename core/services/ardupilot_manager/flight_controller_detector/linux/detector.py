# pylint: disable=unused-import
from typing import List, Optional, Type

from loguru import logger

from flight_controller_detector.linux.argonot import Argonot
from flight_controller_detector.linux.linux_boards import LinuxFlightController
from flight_controller_detector.linux.navigator import NavigatorPi4, NavigatorPi5


class LinuxFlightControllerDetector:
    # for sanity reasons, let's assume a linux board never gets disconnected
    # this will prevent a lot of loading/unloading of modules and overlays in the future
    previously_detected: Optional["LinuxFlightController"] = None

    @classmethod
    def detect_boards(cls, ignore_cache: bool = False) -> Optional["LinuxFlightController"]:
        if cls.previously_detected and not ignore_cache:
            return cls.previously_detected

        for candidate in LinuxFlightController.get_all_boards():
            logger.info(f"Detecting Linux board: {candidate.__name__}")
            if candidate().detect():
                logger.info(f"Detected Linux board: {candidate.__name__}")
                cls.previously_detected = candidate()
                return candidate()
        return None
