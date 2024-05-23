import abc
import json
import pathlib
from typing import Any, ClassVar, Dict, List

from loguru import logger
from pydantic import BaseModel, ValidationError

from commonwealth.settings.exceptions import (
    BadAttributes,
    BadSettingsClassNaming,
    BadSettingsFile,
    MigrationFail,
    SettingsFromTheFuture,
)


class PydanticSettings(BaseModel):
    VERSION: int = 0
    STATIC_VERSION: ClassVar[int]

    def __init__(self, **kwargs: Dict[str, Any]) -> None:
        super().__init__(**kwargs)
        direct_children: List[Any] = []
        for child in type(self).mro():
            if child == PydanticSettings:
                break
            if issubclass(child, PydanticSettings):
                direct_children.append(child)
        for child in reversed(direct_children):
            try:
                v = int("".join(filter(str.isdigit, child.__name__)))
            except ValueError as e:
                raise BadSettingsClassNaming(
                    f"{child.__name__} is not a valid settings class name, valid names should contain as number. Eg: V1"
                ) from e
            self.VERSION = v
            child.STATIC_VERSION = v  # type: ignore

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
            try:
                new = self.parse_obj(result)
                self.__dict__.update(new.__dict__)
            except ValidationError as e:
                raise BadSettingsFile(f"Settings file contains invalid data: {e}") from e

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
            settings_file.write(self.json(indent=4))

    def reset(self) -> None:
        """Reset internal data to default values"""
        logger.debug("Resetting settings")
        new = self.__class__()
        self.__dict__.update(new.__dict__)
