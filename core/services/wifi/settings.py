from typing import Any, Dict

from commonwealth.settings.settings import PydanticSettings


class SettingsV1(PydanticSettings):
    hotspot_enabled: bool = False
    hotspot_ssid: str = "BlueOS"
    hotspot_password: str = "blueosap"
    smart_hotspot_enabled: bool = False

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
