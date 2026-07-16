from typing import Any, Dict, List

from commonwealth.settings.settings import PydanticSettings
from pydantic import BaseModel, Field


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


class SettingsV1(PydanticSettings):
    specs: List[BridgeSettingsSpecV1] = Field(default_factory=list)

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION


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


class SettingsV2(SettingsV1):
    specsv2: List[BridgeSettingsSpecV2] = Field(default_factory=list)

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
