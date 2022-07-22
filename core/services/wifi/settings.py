from typing import Any, Dict

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
