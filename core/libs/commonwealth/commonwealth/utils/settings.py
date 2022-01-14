from typing import Any, Dict, Optional
from loguru import logger
import appdirs
import os
import pathlib
import json
import importlib.util
import time

class NoSettingsFile(ValueError):
    """Settings file does not exist."""

class BadSettingsFile(ValueError):
    """Settings file is not valid."""

class SettingsFromTheFuture(ValueError):
    """Settings file version is from a newer version of the service."""

class OldSettings(ValueError):
    """Settings file version is old."""

class MigrationFail(RuntimeError):
    """Could not apply migration."""

class BadAttributes(BadSettingsFile):
    """Attributes on settings file are not valid for current version."""


class Settings:
    SERVICE_NAME = ''
    VERSION = 0

    def __init__(self, settings_filepath: Optional[pathlib.Path] = None) -> None:
        self.settings_filepath = settings_filepath

        if self.settings_filepath is None:
            logger.warning("Settings filepath not provided. Using default.")
            self.settings_filepath = self.get_default_settings_filepath()

        try:
            self.validate_settings_file()
            self.validate_attributes()
        except NoSettingsFile as error:
            if settings_filepath:
                raise error
            logger.warning(f"Initial settings file not found. Creating a new one on {self.settings_filepath}.")
            self.create_initial_settings_file()
        except BadSettingsFile:
            logger.warning(f"Settings file is broken. Backuping it and creating a new one.")
            self.backup_settings_file()
            self.create_initial_settings_file()

        try:
            self.validate_version()
        except OldSettings:
            logger.warning("Old settings file detected. Trying to perform upgrade.")
            self.upgrade_to_latest_version()

    def get_content(self) -> Dict[str, Any]:
        with open(self.settings_filepath, encoding='utf-8') as file:
            content = json.load(file)
        return content

    def save_content(self, content: Dict[str, Any]) -> None:
        with open(self.settings_filepath, 'w', encoding='utf-8') as file:
            json.dump(content, file, indent=2)

    def get_attributes(self, attribute_name: Optional[str] = None) -> Any:
        content = self.get_content()
        saved_attributes = content.get('attributes')

        if attribute_name is None:
            return saved_attributes
        else:
            try:
                return saved_attributes[attribute_name]
            except Exception as error:
                raise ValueError(f"Attribute '{attribute_name}' not available on settings content.") from error

    def save_attribute(self, attribute_name: str, attribute: Any) -> Any:
        content = self.get_content()
        saved_attributes = content.get('attributes')

        logger.debug(f"Removing old attribute '{attribute_name}' from settings content.")
        old_attribute_value = saved_attributes.pop(attribute_name, None)
        if old_attribute_value:
            logger.debug(f"Old attribute value was: {old_attribute_value}.")
        else: 
            logger.debug(f"No old value found for attribute '{attribute_name}'.")

        logger.debug(f"Saving new data for '{attribute_name}' on settings file.")
        saved_attributes[attribute_name] = attribute
        content['attributes'] = saved_attributes

        self.save_content(content)

    def get_initial_content(self) -> Dict[str, Any]:
        return {
            "service_name": self.SERVICE_NAME,
            "settings_version": self.VERSION,
            "attributes": {},
        }

    def create_initial_settings_file(self) -> None:
        content = self.get_initial_content()
        self.save_content(content)

    def get_default_settings_filepath(self) -> None:
        service_config_path = appdirs.user_config_dir(self.SERVICE_NAME)
        return pathlib.Path(service_config_path, "settings.json")

    def validate_settings_file(self) -> None:
        if not self.settings_filepath.exists():
            raise NoSettingsFile(f"Path {self.settings_filepath} does not exist.")

        if not self.settings_filepath.is_file():
            raise BadSettingsFile(f"Path {self.settings_filepath} is not a file.")

        try:
            content = self.get_content()
            service_name = content.get('service_name')
            if service_name is None:
                raise ValueError("'service_name' variable not found on settings file.")
            if service_name != self.SERVICE_NAME:
                raise ValueError("'service_name' variable from settings file diverges from service's name.")
            settings_version = content.get('settings_version')
            if settings_version is None:
                raise ValueError("'settings_version' variable not found on settings file.")
            attributes = content.get('attributes')
            if attributes is None:
                raise ValueError("'attributes' variable not found on settings file.")
        except json.decoder.JSONDecodeError as error:
            raise BadSettingsFile(f"Settings file '{self.settings_filepath}' is broken. {error}") from error
        except Exception as error:
            raise BadSettingsFile(f"'{self.settings_filepath}' is not a valid settings file. {error}") from error

    def validate_version(self) -> None:
        content = self.get_content()
        if content['settings_version'] > self.VERSION:
            raise SettingsFromTheFuture("Settings file is from a newer version of the service.")
        if self.VERSION > content['settings_version']:
            raise OldSettings("Settings file is old and need to be updated.")

    def validate_attributes(self) -> None:
        # Test settings-file schema
        pass

    def backup_settings_file(self) -> None:
        backup_path = self.settings_filepath.parent / (self.settings_filepath.stem + f"_{int(time.time())}" + '.bkp')
        self.settings_filepath.rename(backup_path)

    def update_settings_version(self) -> None:
        content = self.get_content()
        content["settings_version"] = self.VERSION

    def migrate_from_previous_version(self) -> None:
        pass

    def upgrade_to_latest_version(self) -> None:
        content = self.get_content()
        file_version = content['settings_version']

        if file_version <= 0:
            raise BadSettingsFile("Settings version should be equal or bigger than 1.")

        if file_version <= self.VERSION:
            super().upgrade_to_latest_version()
            self.migrate_from_previous_version()
            self.update_settings_version()

class ArdupilotManagerSettingsV1(Settings):
    SERVICE_NAME = "ardupilot-manager"
    VERSION = 1

class ArdupilotManagerSettingsV2(ArdupilotManagerSettingsV1):
    VERSION = 2

    def migrate_from_previous_version(self) -> None:
        old_attributes = self.get_attributes()
        old_endpoints = old_attributes.get("endpoints") or []
        new_endpoints = [{**endpoint, "owner":"undefined_owner"} for endpoint in old_endpoints]
        self.save_attribute("endpoints", new_endpoints)


if __name__ == "__main__":
    settings = ArdupilotManagerSettingsV2(settings_filepath=pathlib.Path(os.path.dirname(__file__), "settings.json"))

    saved_endpoints = settings.get_attributes('endpoints')
    logger.info(f"Saved endpoints: {saved_endpoints}.")

    endpoints = saved_endpoints
    endpoints.append({"name": "e4", "port": 0, "owner": "rafael"})
    logger.info(f"Modified endpoints: {endpoints}.")

    settings.save_attribute("endpoints", endpoints)
    all_attributes = settings.get_attributes()
    logger.info(f"Modified saved attributes: {all_attributes}.")
