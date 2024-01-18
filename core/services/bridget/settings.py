from typing import Any, Dict

import pykson  # type: ignore
from commonwealth.settings import settings


class BridgeSettingsSpecV1(pykson.JsonObject):
    serial_path = pykson.StringField()
    baudrate = pykson.IntegerField()
    ip = pykson.StringField()
    udp_port = pykson.IntegerField()

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


class BridgeSettingsSpecV2(pykson.JsonObject):
    udp_target_port = pykson.IntegerField()
    udp_listen_port = pykson.IntegerField()
    serial_path = pykson.StringField()
    baudrate = pykson.IntegerField()
    ip = pykson.StringField()

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


class SettingsV2(SettingsV1):
    VERSION = 2
    specsv2 = pykson.ObjectListField(BridgeSettingsSpecV2)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV2.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.VERSION:
            return

        if data["VERSION"] < SettingsV2.VERSION:
            super().migrate(data)

            data["VERSION"] = SettingsV2.VERSION
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
