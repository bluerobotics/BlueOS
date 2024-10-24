# This file is used to define general configurations for the app
from collections import namedtuple
from pathlib import Path

import appdirs

SERVICE_NAME = "autopilot-manager"


SETTINGS_PATH = Path(appdirs.user_config_dir(SERVICE_NAME))
LOG_PATH = Path.joinpath(SETTINGS_PATH, "logs")
FIRMWARE_PATH = Path.joinpath(SETTINGS_PATH, "firmware")
USER_FIRMWARE_PATH = Path("/usr/blueos/userdata/firmware")

BLUE_OS_FILES_PATH = Path.joinpath(Path.home(), "blueos-files")
DEFAULTS_PATH = Path.joinpath(BLUE_OS_FILES_PATH, "ardupilot-manager/default")

@staticmethod
    def create_app_folders() -> None:
        """Create the necessary folders for proper app function."""
        for folder in Settings.app_folders:
            try:
                Path.mkdir(folder, parents=True, exist_ok=True)
            except FileExistsError:
                logger.warning(f"Found file {folder} where a folder should be. Removing file and creating folder.")
                Path.unlink(folder)
                Path.mkdir(folder)

StaticFile = namedtuple("StaticFile", "parent filename url")
DEFAULT_RESOURCES = [
    StaticFile(
        DEFAULTS_PATH, "ardupilot_navigator", "https://firmware.ardupilot.org/Sub/stable-4.5.0/navigator/ardusub",
    ),
    StaticFile(
        DEFAULTS_PATH, "ardupilot_navigator", "https://firmware.ardupilot.org/Sub/stable-4.5.0/navigator64/ardusub",
    ),
    StaticFile(
        DEFAULTS_PATH, "ardupilot_pixhawk1", "https://firmware.ardupilot.org/Sub/stable-4.5.0/Pixhawk1/ardusub.apj"
    ),
    StaticFile(
        DEFAULTS_PATH, "ardupilot_pixhawk4", "https://firmware.ardupilot.org/Sub/stable-4.5.0/Pixhawk4/ardusub.apj"
    ),
]


__all__ = [
    "SERVICE_NAME",
    "DEFAULT_RESOURCES",
    "SETTINGS_PATH",
    "LOG_PATH",
    "FIRMWARE_PATH",
    "USER_FIRMWARE_PATH",
    "BLUE_OS_FILES_PATH",
    "DEFAULTS_PATH",
]
