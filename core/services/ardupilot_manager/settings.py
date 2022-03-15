import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Union, cast

import appdirs
from loguru import logger

SERVICE_NAME = "ardupilot-manager"


class Settings:
    app_name = SERVICE_NAME
    settings_path = Path(appdirs.user_config_dir(app_name))
    settings_file = Path.joinpath(settings_path, "settings.json")
    firmware_folder = Path.joinpath(settings_path, "firmware")
    log_path = Path.joinpath(settings_path, "logs")
    app_folders = [settings_path, firmware_folder, log_path]

    blueos_files_folder = Path.joinpath(Path.home(), "blueos-files")
    defaults_folder = Path.joinpath(blueos_files_folder, "ardupilot-manager/default")

    def __init__(self) -> None:
        self.root: Dict[str, Union[int, Dict[str, Any]]] = {"version": 0, "content": {}}

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

    def create_settings_file(self) -> None:
        """Create settings file."""
        try:
            if not Path.is_file(self.settings_file):
                with open(self.settings_file, "w+", encoding="utf-8") as file:
                    logger.info(f"Creating settings file: {self.settings_file}")
                    json.dump(self.root, file, sort_keys=True, indent=4)

        except OSError as error:
            logger.error(
                f"Could not create settings files: {error}\n No settings will be loaded or saved during this session."
            )

    @property
    def content(self) -> Dict[str, Any]:
        return cast(Dict[str, Any], self.root["content"])

    @property
    def version(self) -> int:
        return cast(int, self.root["version"])

    def settings_exist(self) -> bool:
        """Check if settings file exist

        Returns:
            bool: True if it exist
        """
        return Path.is_file(self.settings_file)

    def load(self) -> bool:
        """Load settings from file

        Returns:
            bool: False if failed
        """
        if not self.settings_exist():
            logger.error(f"User settings does not exist on {self.settings_file}.")
            return False

        data = None
        try:
            with open(self.settings_file, encoding="utf-8") as file:
                data = json.load(file)
                if data["version"] != self.root["version"]:
                    logger.error("User settings does not match with our supported version.")
                    return False

                self.root = data
        except Exception as error:
            logger.error(f"Failed to fetch data from file ({self.settings_file}): {error}")
            logger.debug(data)

        return True

    def save(self, content: Dict[str, Any]) -> None:
        """Save content to file

        Args:
            content (list): Configuration list
        """
        # We don't want to write in disk if there is nothing different to write
        if self.root["content"] == content:
            logger.info("No new data. Not updating settings file.")
            return

        self.root["content"] = deepcopy(content)

        try:
            Path.mkdir(self.settings_path, exist_ok=True)

            with open(self.settings_file, "w+", encoding="utf-8") as file:
                logger.info(f"Updating settings file: {self.settings_file}")
                json.dump(self.root, file, sort_keys=True, indent=4)
        except Exception as error:
            logger.warning(f"Could not save settings to disk: {error}")
