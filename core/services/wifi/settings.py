from typing import Any, Dict, Optional

from commonwealth.settings.settings import PydanticSettings


class SettingsV1(PydanticSettings):
    hotspot_enabled: Optional[bool] = None
    hotspot_ssid: Optional[str] = None
    hotspot_password: Optional[str] = None
    smart_hotspot_enabled: Optional[bool] = None
    # Optional, so existing version-1 files load it as None without a migration
    hotspot_interface: Optional[str] = None

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
