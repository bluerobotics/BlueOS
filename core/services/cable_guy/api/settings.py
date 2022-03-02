import json
import os
from typing import Any, Dict, List

import appdirs
from loguru import logger


class Settings:
    app_name = "cable-guy"
    settings_path = appdirs.user_config_dir(app_name)
    settings_file = os.path.join(settings_path, "settings.json")

    def __init__(self) -> None:
        self.root: Dict[str, Any] = {"version": 0, "content": {}}

    def settings_exist(self) -> bool:
        """Check if settings file exist

        Returns:
            bool: True if it exist
        """
        return os.path.isfile(self.settings_file)

    def load(self) -> bool:
        """Load settings from file

        Returns:
            bool: False if failed
        """
        if not self.settings_exist():
            logger.warning(f"User settings does not exist: {self.settings_file}")
            return False

        data = None
        try:
            with open(self.settings_file, encoding="utf-8") as file:
                data = json.load(file)
                if data["version"] != self.root["version"]:
                    logger.warning("User settings does not match with our supported version.")
                    return False

                self.root = data
        except Exception as exception:
            logger.warning(f"Failed to fetch data from file ({self.settings_file}): {exception}")
            logger.warning(data)

        return True

    def save(self, content: List[Any]) -> None:
        """Save content to file

        Args:
            content (list): Configuration list
        """
        # We don't want to write in disk if there is nothing different to write
        if self.root["content"] == content:
            return

        self.root["content"] = content

        if not os.path.exists(self.settings_path):
            os.makedirs(self.settings_path)

        with open(self.settings_file, "w+", encoding="utf-8") as file:
            logger.debug(f"Updating settings file: {self.settings_file}")
            json.dump(self.root, file, sort_keys=True, indent=4)
