import json
from pathlib import Path
from typing import Any

import appdirs
from commonwealth.settings.settings import PydanticSettings
from config import SERVICE_NAME
from loguru import logger
from mavlink_proxy.Endpoint import Endpoint
from pydantic import field_validator
from typedefs import FlightController, Serial, SITLFrame
from typing_extensions import override

SERVICE_NAME = "ardupilot-manager"


class SettingsV1(PydanticSettings):
    VERSION: int = 0

    firmware_folder: Path = Path(appdirs.user_config_dir(SERVICE_NAME)) / "firmware"
    defaults_folder: Path = Path.home() / "blueos-files/ardupilot-manager/default"
    user_firmware_folder: Path = Path("/usr/blueos/userdata/firmware")
    log_path: Path = Path(appdirs.user_config_dir(SERVICE_NAME)) / "logs"

    serials: list[Serial] = []
    sitl_frame: SITLFrame = SITLFrame.UNDEFINED
    start_on_boot: bool = True
    preferred_router: str | None = None
    preferred_board: FlightController | None = None
    endpoints: set[Endpoint] = set()
    manual_board_master_endpoint: Endpoint | None = None

    @field_validator("serials", mode="before")
    @classmethod
    def keep_valid_serials(cls, value: Any) -> list[Serial]:
        if not value:
            return []
        valid: list[Serial] = []
        if isinstance(value, list):
            for entry in value:
                try:
                    valid.append(entry if isinstance(entry, Serial) else Serial.model_validate(entry))
                except Exception as error:
                    logger.warning(f"Ignoring invalid serial settings entry {entry}: {error}")
        return valid

    @override
    def migrate(self, data: dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION

    @override
    def on_settings_created(self, _: Path) -> None:
        migrate_from_old_settings(self)

    def create_app_folders(self) -> None:
        """Create the necessary folders for the app to function properly."""
        for folder in (self.firmware_folder, self.log_path, self.user_firmware_folder):
            try:
                Path.mkdir(folder, parents=True, exist_ok=True)
            except FileExistsError:
                logger.warning(f"Found file {folder} where a folder should be. Removing file and creating folder.")
                Path.unlink(folder)
                Path.mkdir(folder)


class Settings:
    app_name = SERVICE_NAME
    settings_path = Path(appdirs.user_config_dir(app_name))
    settings_file = Path.joinpath(settings_path, "settings.json")
    startup_settings_file = Path(appdirs.user_config_dir("bootstrap"), "startup.json")
    firmware_folder = Path.joinpath(settings_path, "firmware")
    user_firmware_folder = Path("/usr/blueos/userdata/firmware")
    log_path = Path.joinpath(settings_path, "logs")
    app_folders = [settings_path, firmware_folder, log_path, user_firmware_folder]

    blueos_files_folder = Path.joinpath(Path.home(), "blueos-files")
    defaults_folder = Path.joinpath(blueos_files_folder, "ardupilot-manager/default")
    sitl_frame = SITLFrame.UNDEFINED
    preferred_router: Optional[str] = None

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
