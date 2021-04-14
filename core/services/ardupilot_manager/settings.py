import json
import pprint
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Union, cast
from warnings import warn

import appdirs


class Settings:
    app_name = "ardupilot-manager"
    settings_path = Path(appdirs.user_config_dir(app_name))
    settings_file = Path.joinpath(settings_path, "settings.json")
    firmware_path = Path.joinpath(settings_path, "firmware")

    def __init__(self) -> None:
        self.root: Dict[str, Union[int, Dict[str, Any]]] = {"version": 0, "content": {}}

    def create_settings(self) -> None:
        """Create settings files and folders."""
        try:
            Path.mkdir(self.settings_path, exist_ok=True)
            Path.mkdir(self.firmware_path, exist_ok=True)
            if not Path.is_file(self.settings_file):
                with open(self.settings_file, "w+") as file:
                    print(f"Creating settings file: {self.settings_file}")
                    json.dump(self.root, file, sort_keys=True, indent=4)

        except OSError as error:
            warn(f"Could not create settings files: {error}\n No settings will be loaded or saved during this session.")

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
            warn(f"User settings does not exist on {self.settings_file}.")
            return False

        data = None
        try:
            with open(self.settings_file) as file:
                data = json.load(file)
                if data["version"] != self.root["version"]:
                    warn("User settings does not match with our supported version.")
                    return False

                self.root = data
        except Exception as error:
            warn(f"Failed to fetch data from file ({self.settings_file}): {error}")
            pprint.pprint(data)

        return True

    def save(self, content: Dict[str, Any]) -> None:
        """Save content to file

        Args:
            content (list): Configuration list
        """
        # We don't want to write in disk if there is nothing different to write
        if self.root["content"] == content:
            print("No new data. Not updating settings file.")
            return

        self.root["content"] = deepcopy(content)

        try:
            Path.mkdir(self.settings_path, exist_ok=True)

            with open(self.settings_file, "w+") as file:
                print(f"Updating settings file: {self.settings_file}")
                json.dump(self.root, file, sort_keys=True, indent=4)
        except Exception as error:
            warn(f"Could not save settings to disk: {error}")
