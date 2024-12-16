import appdirs
from pathlib import Path

# This file is used to define general configurations for the app

SERVICE_NAME = "ardupilot-manager"

# Paths

SETTINGS_PATH = Path(appdirs.user_config_dir(SERVICE_NAME))

LOG_FOLDER = Path.joinpath(SETTINGS_PATH, "logs")
FIRMWARE_FOLDER = Path.joinpath(SETTINGS_PATH, "firmware")
USER_FIRMWARE_FOLDER = Path("/usr/blueos/userdata/firmware")

APP_FOLDERS = [SETTINGS_PATH, FIRMWARE_FOLDER, LOG_FOLDER, USER_FIRMWARE_FOLDER]

blueos_files_folder = Path.joinpath(Path.home(), "blueos-files")
defaults_folder = Path.joinpath(blueos_files_folder, "ardupilot-manager/default")

__all__ = ["SERVICE_NAME"]
