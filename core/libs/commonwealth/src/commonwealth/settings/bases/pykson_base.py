import abc
import json
import os
import pathlib
from typing import Any, Dict

import pykson  # type: ignore
from commonwealth.settings.exceptions import (
    BadAttributes,
    BadSettingsFile,
    MigrationFail,
    SettingsFromTheFuture,
)
from loguru import logger
from pykson import Field, Pykson


class PyksonSettings(pykson.JsonObject):
    """Base settings class for Pykson serializer"""

    VERSION = pykson.IntegerField(default_value=0)

    def __init__(self, *args: str, **kwargs: int) -> None:
        # Make sure that all attributes are derivated from Pykson.Field
        for key, item in type(self).__dict__.items():
            # Remove default attributes and version tracker from validation
            if key in ["__doc__", "__module__", "VERSION"]:
                continue
            if callable(item):
                continue
            assert isinstance(
                item, Field
            ), f"Class attributes must be from Pykson.Field or derivated: {type(item)}: {key}"
        super().__init__(*args, **kwargs)

    @abc.abstractmethod
    def migrate(self, data: Dict[str, Any]) -> None:
        """Function used to migrate from previous settings version

        Args:
            data (dict): Data from the previous version settings
        """
        raise RuntimeError("Migrating the settings file does not appears to be possible.")

    def load(self, file_path: pathlib.Path) -> None:
        """Load settings from file

        Args:
            file_path (pathlib.Path): Path for settings file
        """
        if not file_path.exists():
            raise RuntimeError(f"Settings file does not exist: {file_path}")

        logger.debug(f"Loading settings from file: {file_path}")
        with open(file_path, encoding="utf-8") as settings_file:
            result = json.load(settings_file)

            if "VERSION" not in result.keys():
                raise BadSettingsFile(f"Settings file does not appears to contain a valid settings format: {result}")

            version = result["VERSION"]

            if version <= 0:
                raise BadAttributes("Settings file contains invalid version number")

            if version > self.VERSION:
                raise SettingsFromTheFuture(
                    f"Settings file comes from a future settings version: {version}, "
                    f"latest supported: {self.VERSION}, tomorrow does not exist"
                )

            if version < self.VERSION:
                self.migrate(result)
                version = result["VERSION"]

            if version != self.VERSION:
                raise MigrationFail("Migrate chain failed to update to the latest settings version available")

            # Copy new content to settings class
            new = Pykson().from_json(result, self.__class__)
            self.__dict__.update(new.__dict__)

    def save(self, file_path: pathlib.Path) -> None:
        """Save settings to file

        Args:
            file_path (pathlib.Path): Path for the settings file
        """
        # Path for settings file does not exist, lets ensure that it does
        parent_path = file_path.parent.absolute()
        parent_path.mkdir(parents=True, exist_ok=True)

        # Prepare data prior to operation
        logger.debug(f"Saving settings on: {file_path}")
        json_data = json.dumps(json.loads(Pykson().to_json(self)), indent=4)

        # Create a temporary file in same directory, write and rename it to the original file
        temp_file = file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as settings_file:
            settings_file.write(json_data)
            # Ensure data is written to disk
            settings_file.flush()
            os.fsync(settings_file.fileno())
        # Replace the original file with the temporary file, this operation is atomic if in the same filesystem
        # https://docs.python.org/3/library/os.html#os.replace
        temp_file.replace(file_path)

    def reset(self) -> None:
        """Reset internal data to default values"""
        logger.debug("Resetting settings")
        new = self.__class__()
        self.__dict__.update(new.__dict__)
