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


class Settings:
    def __init__(self, service_name: str, settings_version: int, settings_filepath: Optional[pathlib.Path] = None) -> None:
        self.service_name = service_name
        self.settings_version = settings_version
        self.settings_filepath = settings_filepath

        if self.settings_filepath is None:
            logger.warning("Settings filepath not provided. Using default.")
            self.settings_filepath = self.get_default_settings_filepath()

        try:
            self.validate_settings_file()
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
            self.upgrade_settings_file()

    def get_content(self) -> Dict[str, Any]:
        with open(self.settings_filepath, encoding='utf-8') as file:
            content = json.load(file)
        return content

    def save_content(self, content: Dict[str, Any]) -> None:
        with open(self.settings_filepath, 'w', encoding='utf-8') as file:
            json.dump(content, file, indent=2)

    def create_initial_settings_file(self) -> None:
        content = self.get_initial_content()
        self.save_content(content)

    def get_initial_content(self) -> Dict[str, Any]:
        return {
            "service_name": self.service_name,
            "settings_version": self.settings_version,
            "attributes": {},
        }

    def get_default_settings_filepath(self) -> None:
        service_config_path = appdirs.user_config_dir(self.service_name)
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
        if content['settings_version'] > self.settings_version:
            raise SettingsFromTheFuture("Settings file is from a newer version of the service.")
        if self.settings_version > content['settings_version']:
            raise OldSettings("Settings file is old and need to be updated.")

    def backup_settings_file(self) -> None:
        backup_path = self.settings_filepath.parent / (self.settings_filepath.stem + f"_{int(time.time())}" + '.bkp')
        self.settings_filepath.rename(backup_path)

    def upgrade_settings_file(self) -> None:
        content = self.get_content()
        migrate_versions = range(content['settings_version'] + 1, self.settings_version + 1)
        migration_files = [self.migration_path(version) for version in migrate_versions]
        for file in migration_files:
            if not file.exists():
                raise MigrationFail(f"Migration file '{file}' not found. Cannot perform migration.")
            self.apply_migration(file)

    @staticmethod
    def migration_name(desired_version: int) -> str:
        return f"migration_{desired_version-1}_to_{desired_version}.py"

    def migration_path(self, desired_version: int) -> pathlib.Path:
        settings_dir = self.settings_filepath.parent
        migration_name = self.migration_name(desired_version)
        return settings_dir.joinpath(migration_name)

    def apply_migration(self, migration_file: pathlib.Path) -> None:
        try:
            spec = importlib.util.spec_from_file_location("migration_module", str(migration_file))
            migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration_module)
            migration_module.migrate(self.settings_filepath)
        except Exception as error:
            raise MigrationFail(
                f"Failed to migrate '{self.settings_filepath}' with instructions on '{migration_file}'."
            ) from error

    def get_attribute(self, attribute: Optional[str] = None) -> Any:
        content = self.get_content()
        saved_attributes = content.get('attributes')
        if not attribute:
            return saved_attributes
        else:
            try:
                return saved_attributes[attribute]
            except Exception as error:
                raise ValueError(f"attribute '{attribute}' not available on settings content.") from error

    def save_attribute(self, attribute_name: str, attribute: Any) -> Any:
        content = self.get_content()
        saved_attributes = content.get('attributes')
        logger.debug(f"Removing attribute '{attribute_name}' from settings content.")
        old_attribute_value = saved_attributes.pop(attribute_name, None)
        if old_attribute_value:
            logger.debug(f"Old attribute value: {old_attribute_value}.")
        else: 
            logger.debug(f"No old value found for attribute '{attribute_name}'.")

        logger.debug(f"Saving new data for '{attribute_name}' on settings file.")
        saved_attributes[attribute_name] = attribute
        content['attributes'] = saved_attributes

        self.save_content(content)


if __name__ == "__main__":
    settings = Settings(
        service_name='ardupilot-manager',
        settings_version=2,
        settings_filepath=pathlib.Path(os.path.dirname(__file__), "settings.json")
    )

    saved_endpoints = settings.get_attribute('endpoints')
    logger.info(f"Saved endpoints: {saved_endpoints}.")

    endpoints = saved_endpoints
    endpoints.append({"name": "e4", "port": 0, "owner": "rafael"})
    logger.info(f"Current modified endpoints: {endpoints}.")

    settings.save_attribute('endpoints', endpoints)
    all_attributes = settings.get_attribute()
    logger.info(f"All attributes: {all_attributes}.")
