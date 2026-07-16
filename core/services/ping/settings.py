from typing import Any, Dict, List

from commonwealth.settings.settings import PydanticSettings
from pydantic import BaseModel, Field


class Ping1dSettingsSpecV1(BaseModel):
    port: str
    mavlink_enabled: bool

    def __str__(self) -> str:
        return f"{self.port} - {self.mavlink_enabled}"

    @staticmethod
    def new(port: str, enabled: bool) -> "Ping1dSettingsSpecV1":
        return Ping1dSettingsSpecV1(port=port, mavlink_enabled=enabled)


class SettingsV1(PydanticSettings):
    ping1d_specs: List[Ping1dSettingsSpecV1] = Field(default_factory=list)
    # no settings for ping360 as of V1

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
