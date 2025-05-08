import abc
import json
import pathlib
from typing import Any, Dict

import pykson  # type: ignore
from loguru import logger
from pykson import Field, Pykson

from commonwealth.settings.exceptions import (
    BadAttributes,
    BadSettingsFile,
    MigrationFail,
    SettingsFromTheFuture,
)


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

        with open(file_path, "w", encoding="utf-8") as settings_file:
            logger.debug(f"Saving settings on: {file_path}")
            settings_file.write(json.dumps(json.loads(Pykson().to_json(self)), indent=4))

    def reset(self) -> None:
        """Reset internal data to default values"""
        logger.debug("Resetting settings")
        new = self.__class__()
        self.__dict__.update(new.__dict__)
