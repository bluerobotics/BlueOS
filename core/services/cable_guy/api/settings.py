import json
import pathlib
from typing import Any, Dict, Sequence

from commonwealth.settings.settings import PydanticSettings

from config import DEFAULT_NETWORK_INTERFACES
from typedefs import AddressMode, NetworkInterface, NetworkInterfaceV1


def sanitize_old_settings_file(path: pathlib.Path) -> None:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Modify old cases of BackupServer to Server in old settings since it will case issues in downgrading
    for iface in data["content"]:
        for address in iface["addresses"]:
            if address["mode"] == AddressMode.BackupServer:
                address["mode"] = AddressMode.Unmanaged

    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


class SettingsV1(PydanticSettings):
    content: Sequence[NetworkInterfaceV1] = DEFAULT_NETWORK_INTERFACES

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION

    def on_settings_created(self, file_path: pathlib.Path) -> None:
        if self.VERSION not in (SettingsV1.STATIC_VERSION, SettingsV1.STATIC_VERSION + 1):
            return

        settings_v1_file = file_path.parent / "settings-1.json"
        if settings_v1_file.exists():
            # If settings v1 already exist, we don't re initialize them
            return

        # If we have some old settings, let's try to use them
        try:
            old_settings_file_path = file_path.parent / "settings.json"

            with open(old_settings_file_path, "r", encoding="utf-8") as file:
                self.content = [NetworkInterface.parse_obj(iface) for iface in json.load(file)["content"]]

            # TODO: Remove the patch bellow around BlueOS 1.5.0 since it's purpose is only sanitizing the settings
            # that may have been corrupted by 1.4.0-beta.17 and 1.4.0-beta.18
            sanitize_old_settings_file(old_settings_file_path)
        except Exception:
            pass


class SettingsV2(SettingsV1):
    content: Sequence[NetworkInterface] = DEFAULT_NETWORK_INTERFACES

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV2.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV2.STATIC_VERSION

        # Transfer routes from default settings, falling back to empty list
        default_routes_map = {net.name: net.routes for net in self.content}
        for iface in data["content"]:
            iface["routes"] = default_routes_map.get(iface["name"], [])
