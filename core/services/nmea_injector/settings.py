from typing import Any, Dict

import pykson  # type: ignore
from commonwealth.settings import settings


class NmeaInjectorSettingsSpecV1(pykson.JsonObject):
    kind = pykson.StringField()
    port = pykson.IntegerField()
    component_id = pykson.IntegerField()

    def __eq__(self, other: object) -> Any:
        if isinstance(other, NmeaInjectorSettingsSpecV1):
            return self.kind == other.kind and self.port == other.port
        return False


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    specs = pykson.ObjectListField(NmeaInjectorSettingsSpecV1)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
