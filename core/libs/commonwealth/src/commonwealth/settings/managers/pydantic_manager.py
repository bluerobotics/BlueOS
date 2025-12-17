import pathlib
import re
from typing import Any, Dict, Optional, Type

import appdirs
from commonwealth.settings.bases.pydantic_base import PydanticSettings
from commonwealth.utils.events import events
from loguru import logger


class PydanticManager:
    SETTINGS_NAME_PREFIX = "settings-"

    def __init__(
        self,
        project_name: str,
        settings_type: Type[PydanticSettings],
        config_folder: Optional[pathlib.Path] = None,
        load: bool = True,
    ) -> None:
        assert project_name, "project_name should be not empty"
        assert issubclass(settings_type, PydanticSettings), "settings_type should use PydanticSettings as subclass"

        self.project_name = project_name.lower()
        self.config_folder = (
            config_folder.joinpath(self.project_name)
            if config_folder
            else pathlib.Path(appdirs.user_config_dir(self.project_name))
        )
        self.config_folder.mkdir(parents=True, exist_ok=True)
        self.settings_type = settings_type
        self._settings: Optional[PydanticSettings] = None
        self._initial_event_emitted = False
        logger.debug(
            f"Starting {project_name} settings with {settings_type.__name__}, configuration path: {config_folder}"
        )
        if load:
            self.load()

    @property
    def settings(self) -> Any:
        """Getter point for settings

        Returns:
            [Type[PydanticSettings]]: The settings defined in the constructor
        """
        if not self._settings:
            self.load()

        return self._settings

    @settings.setter
    def settings(self, value: Any) -> None:
        """Setter point for settings. Save settings for every change

        Args:
            value ([Type[PydanticSettings]]): The settings defined in the constructor
        """
        if not self._settings:
            self.load()

        self._settings = value
        self.save()

    def settings_file_path(self) -> pathlib.Path:
        """Return the settings file for the version specified in the constructor settings

        Returns:
            pathlib.Path: Path for the settings file
        """
        # Due to the fact that the static version is created in the inheritance chain instantiation, we need to
        # instantiate the class to get the static version
        version = self.settings_type().STATIC_VERSION

        return self.config_folder.joinpath(f"{PydanticManager.SETTINGS_NAME_PREFIX}{version}.json")

    @staticmethod
    def load_from_file(settings_type: Type[PydanticSettings], file_path: pathlib.Path) -> Any:
        """Load settings from a generic location and settings type

        Args:
            settings_type (PydanticSettings): Settings type that inherits from PydanticSettings.
            file_path (pathlib.Path): Path for a valid settings file

        Returns:
            Any: The settings based on settings_type
        """
        assert issubclass(settings_type, PydanticSettings), "settings_type should use PydanticSettings as subclass"

        settings_data = settings_type()

        if file_path.exists():
            settings_data.load(file_path)
        else:
            settings_data.save(file_path)

        return settings_data

    def save(self) -> None:
        """Save settings"""
        self.settings.save(self.settings_file_path())
        self._publish_settings_snapshot("save")

    def load(self) -> None:
        """Load settings"""

        # TODO: We could try to restore the settings from the temporary file if the main is not found or valid
        # Clear temporary files that could be left from a previous operation
        self._clear_temp_files()

        def get_settings_version_from_filename(filename: pathlib.Path) -> int:
            result = re.search(f"{PydanticManager.SETTINGS_NAME_PREFIX}(\\d+)", filename.name)
            assert result
            assert len(result.groups()) == 1
            return int(result.group(1))

        # Get all possible settings candidates and sort it by version
        valid_files = [
            possible_file
            for possible_file in self.config_folder.iterdir()
            if possible_file.name.startswith(PydanticManager.SETTINGS_NAME_PREFIX)
        ]
        valid_files.sort(key=get_settings_version_from_filename, reverse=True)

        logger.debug(f"Found possible candidates for settings source: {valid_files}")
        for valid_file in valid_files:
            logger.debug(f"Checking {valid_file} for settings")
            try:
                self._settings = PydanticManager.load_from_file(self.settings_type, valid_file)
                logger.debug(f"Using {valid_file} as settings source")
                self._emit_initial_settings_event()
                return
            except Exception as exception:
                logger.debug("Invalid settings, going to try another file:", exception)

        logger.debug("No valid settings found, using default settings")
        self._settings = self.settings_type()
        self.save()
        self._emit_initial_settings_event()

    def _clear_temp_files(self) -> None:
        """Clear temporary files"""
        for temp_file in self.config_folder.glob("*.tmp"):
            try:
                temp_file.unlink()
            except Exception as exception:
                logger.debug(f"Failed to clear temporary file {temp_file}: {exception}")

    def _serialize_settings(self) -> Optional[Dict[str, Any]]:
        if not self._settings:
            return None
        try:
            if hasattr(self._settings, "model_dump"):
                return self._settings.model_dump()
            return self._settings.dict()
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Failed to serialize settings for event publishing: {exc}")
            return None

    def _publish_settings_snapshot(self, reason: str) -> None:
        serialized = self._serialize_settings()
        if not serialized:
            return
        metadata = {"project": self.project_name, "reason": reason}
        try:
            events.publish_settings(serialized, metadata)
        except Exception as exc:  # pragma: no cover - best effort
            logger.debug(f"Unable to publish settings event: {exc}")

    def _emit_initial_settings_event(self) -> None:
        if self._initial_event_emitted:
            return
        self._initial_event_emitted = True
        self._publish_settings_snapshot("initial-load")
