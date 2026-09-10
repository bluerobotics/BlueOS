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

# pylint: disable=too-many-branches
def migrate_from_old_settings(target_settings: "SettingsV1") -> None:
    path = Path(appdirs.user_config_dir(SERVICE_NAME)) / "settings.json"
    if not path.exists():
        logger.error("Old settings file for ardupilot_manager not found")

    try:
        with path.open(encoding="utf-8") as file:
            data = json.load(file)
        content = data.get("content")
        if not isinstance(content, dict):
            raise ValueError("old settings file is missing a content object")

        serials: list[Serial] = []
        for entry in content.get("serials") or []:
            try:
                serials.append(Serial.model_validate(entry))
            except Exception as error:
                logger.error(f"Entry is invalid! {entry}")
                logger.error(error)
        target_settings.serials = serials

        if "start_on_boot" in content:
            target_settings.start_on_boot = bool(content["start_on_boot"])
        if "preferred_router" in content:
            target_settings.preferred_router = content["preferred_router"]
        try:
            if "sitl_frame" in content:
                target_settings.sitl_frame = SITLFrame(content["sitl_frame"])
        except Exception as error:
            logger.warning(f"Ignoring invalid SITL frame in old settings: {error}")
        try:
            if content.get("preferred_board") is not None:
                target_settings.preferred_board = FlightController.model_validate(content["preferred_board"])
        except Exception as error:
            logger.warning(f"Ignoring invalid preferred board in old settings: {error}")

        endpoints: set[Endpoint] = set()
        for raw in content.get("endpoints") or []:
            endpoint = Endpoint.from_raw(raw)
            if endpoint is None:
                logger.warning(f"Ignoring invalid endpoint record {raw}")
                continue
            endpoints.add(endpoint)
        target_settings.endpoints = endpoints

        if content.get("manual_board_master_endpoint") is not None:
            endpoint = Endpoint.from_raw(content["manual_board_master_endpoint"])
            if endpoint is not None:
                target_settings.manual_board_master_endpoint = endpoint
    except Exception as error:
        logger.warning(f"Failed to migrate ardupilot_manager settings from {path}: {error}")


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
