from typing import Any, Dict

import pykson  # type: ignore
from commonwealth.settings import settings


class Ping1dSettingsSpecV1(pykson.JsonObject):
    port = pykson.StringField()
    mavlink_enabled = pykson.BooleanField()

    def __str__(self) -> str:
        return f"{self.port} - {self.mavlink_enabled}"

    @staticmethod
    def new(port: str, enabled: bool) -> "Ping1dSettingsSpecV1":
        return Ping1dSettingsSpecV1(port=port, mavlink_enabled=enabled)


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    ping1d_specs = pykson.ObjectListField(Ping1dSettingsSpecV1)
    # no settings for ping360 as of V1

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
