import json
from typing import Any, Dict, Optional

import pykson  # type: ignore
from commonwealth.settings import settings


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    hotspot_enabled = pykson.BooleanField()
    hotspot_ssid = pykson.StringField()
    hotspot_password = pykson.StringField()
    smart_hotspot_enabled = pykson.BooleanField()

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION


class SettingsV2(SettingsV1):
    VERSION = 2
    # Stores user-selected mode per interface as JSON: '{"wlan0": "normal", "wlan1": "hotspot"}'
    interface_modes_json = pykson.StringField()
    # Stores per-interface hotspot credentials as JSON:
    # '{"wlan0": {"ssid": "BlueOS", "password": "password"}, "wlan1": {"ssid": "BlueOS-2", "password": "pass2"}}'
    interface_hotspot_credentials_json = pykson.StringField()

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        self.VERSION = SettingsV2.VERSION
        if not self.interface_modes_json:
            self.interface_modes_json = "{}"
        if not self.interface_hotspot_credentials_json:
            self.interface_hotspot_credentials_json = "{}"

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.VERSION:
            return

        if data["VERSION"] < SettingsV2.VERSION:
            super().migrate(data)

        # Migration from version 1 to 2: add new fields
        if "interface_modes_json" not in data:
            data["interface_modes_json"] = "{}"

        # Copy global credentials to wlan0 for backward compatibility
        if "interface_hotspot_credentials_json" not in data:
            global_ssid = data.get("hotspot_ssid", "")
            global_password = data.get("hotspot_password", "")
            if global_ssid and global_password:
                credentials = {"wlan0": {"ssid": global_ssid, "password": global_password}}
                data["interface_hotspot_credentials_json"] = json.dumps(credentials)
            else:
                data["interface_hotspot_credentials_json"] = "{}"

        data["VERSION"] = SettingsV2.VERSION

    def get_interface_modes(self) -> Dict[str, str]:
        """Get interface modes as a dictionary."""
        try:
            result: Dict[str, str] = json.loads(self.interface_modes_json or "{}")
            return result
        except json.JSONDecodeError:
            return {}

    def set_interface_modes(self, modes: Dict[str, str]) -> None:
        """Set interface modes from a dictionary."""
        self.interface_modes_json = json.dumps(modes)

    def get_interface_hotspot_credentials(self, interface: str) -> Optional[Dict[str, str]]:
        """Get hotspot credentials for a specific interface."""
        try:
            all_credentials: Dict[str, Dict[str, str]] = json.loads(self.interface_hotspot_credentials_json or "{}")
            return all_credentials.get(interface)
        except json.JSONDecodeError:
            return None

    def set_interface_hotspot_credentials(self, interface: str, ssid: str, password: str) -> None:
        """Set hotspot credentials for a specific interface."""
        try:
            all_credentials = json.loads(self.interface_hotspot_credentials_json or "{}")
        except json.JSONDecodeError:
            all_credentials = {}
        all_credentials[interface] = {"ssid": ssid, "password": password}
        self.interface_hotspot_credentials_json = json.dumps(all_credentials)

    def get_all_interface_hotspot_credentials(self) -> Dict[str, Dict[str, str]]:
        """Get all interface hotspot credentials."""
        try:
            result: Dict[str, Dict[str, str]] = json.loads(self.interface_hotspot_credentials_json or "{}")
            return result
        except json.JSONDecodeError:
            return {}
