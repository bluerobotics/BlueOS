import json
import pathlib
from typing import Any, Dict, List

from commonwealth.settings.settings import PydanticSettings
from pydantic import BaseModel

OLD_SETTINGS_DIR = "/usr/blueos/userdata/settings/bridget/bridget"


class BridgeSettingsSpecV1(BaseModel):
    serial_path: str
    baudrate: int
    ip: str
    udp_port: int

    @staticmethod
    def from_spec(spec: "BridgeFrontendSpec") -> "BridgeSettingsSpecV1":  # type: ignore
        return BridgeSettingsSpecV1(
            serial_path=spec.serial_path,
            baudrate=spec.baud,
            ip=spec.ip,
            udp_port=spec.udp_port,
        )

    def __eq__(self, other: object) -> Any:
        if isinstance(other, BridgeSettingsSpecV1):
            return self.serial_path == other.serial_path
        return False

class BridgeSettingsSpecV2(BaseModel):
    udp_target_port: int
    udp_listen_port: int
    serial_path: str
    baudrate: int
    ip: str

    @staticmethod
    def from_spec(spec: "BridgeFrontendSpec") -> "BridgeSettingsSpecV2":  # type: ignore
        return BridgeSettingsSpecV2(
            serial_path=spec.serial_path,
            baudrate=spec.baud,
            ip=spec.ip,
            udp_target_port=spec.udp_target_port,
            udp_listen_port=spec.udp_listen_port,
        )

    def __eq__(self, other: object) -> Any:
        if isinstance(other, BridgeSettingsSpecV2):
            return self.serial_path == other.serial_path
        return False


def migrate_from_old_settings(version: int, target_settings: "SettingsV1") -> None:
    """Common method to migrate settings from the old location."""
    old_settings_file_path = pathlib.Path(OLD_SETTINGS_DIR) / f"settings-{version}.json"

    if not old_settings_file_path.exists():
        return

    try:
        with open(old_settings_file_path, "r", encoding="utf-8") as file:
            old_data = json.load(file)

        if version == 1 and "specs" in old_data:
            target_settings.specs = [BridgeSettingsSpecV1.parse_obj(spec) for spec in old_data["specs"]]
        elif version == 2 and "specsv2" in old_data:
            # For V2, we need to cast to SettingsV2 to access specsv2
            if hasattr(target_settings, 'specsv2'):
                target_settings.specsv2 = [BridgeSettingsSpecV2.parse_obj(spec) for spec in old_data["specsv2"]]

    except Exception:
        # If migration fails, just continue with empty settings
        pass


class SettingsV1(PydanticSettings):
    specs: List[BridgeSettingsSpecV1] = []

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION

    def on_settings_created(self, file_path: pathlib.Path) -> None:
        """Handle migration from old settings location when creating new settings."""
        if self.VERSION not in (SettingsV1.STATIC_VERSION, SettingsV1.STATIC_VERSION + 1):
            return

        settings_v1_file = file_path.parent / "settings-1.json"
        if settings_v1_file.exists():
            # If settings v1 already exist, we don't re initialize them
            return

        # Use common migration method
        migrate_from_old_settings(1, self)


class SettingsV2(SettingsV1):
    specsv2: List[BridgeSettingsSpecV2] = []

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV2.STATIC_VERSION:
            super().migrate(data)

            data["VERSION"] = SettingsV2.STATIC_VERSION
            data["specsv2"] = []
            for spec in data["specs"]:
                server = spec["ip"] == "0.0.0.0"
                data["specsv2"].append(
                    {
                        "serial_path": spec["serial_path"],
                        "baudrate": spec["baudrate"],
                        "ip": spec["ip"],
                        "udp_target_port": 0 if server else spec["udp_port"],
                        "udp_listen_port": spec["udp_port"] if server else 0,
                    }
                )

    def on_settings_created(self, file_path: pathlib.Path) -> None:
        """Handle migration from old settings location when creating new settings."""
        if self.VERSION not in (SettingsV2.STATIC_VERSION, SettingsV2.STATIC_VERSION + 1):
            return

        settings_v2_file = file_path.parent / "settings-2.json"
        if settings_v2_file.exists():
            # If settings v2 already exist, we don't re initialize them
            return

        # Use common migration method
        migrate_from_old_settings(2, self)
