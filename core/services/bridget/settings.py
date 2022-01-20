from typing import Any, Dict

import pykson  # type: ignore
from commonwealth.settings import settings


class BridgeSettingsSpecV1(pykson.JsonObject):
    serial_path = pykson.StringField()
    baudrate = pykson.IntegerField()
    ip = pykson.StringField()
    udp_port = pykson.IntegerField()

    @staticmethod
    def from_spec(spec: "BridgeSpec") -> "BridgeSettingsSpecV1":  # type: ignore
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


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    specs = pykson.ObjectListField(BridgeSettingsSpecV1)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
