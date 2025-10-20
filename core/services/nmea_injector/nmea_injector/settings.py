from typing import Any, Dict, List

from commonwealth.settings.settings import PydanticSettings
from pydantic import BaseModel, Field


class NmeaInjectorSettingsSpecV1(BaseModel):
    kind: str
    port: int
    component_id: int

    def __eq__(self, other: object) -> Any:
        if isinstance(other, NmeaInjectorSettingsSpecV1):
            return self.kind == other.kind and self.port == other.port
        return False


class SettingsV1(PydanticSettings):
    specs: List[NmeaInjectorSettingsSpecV1] = Field(default_factory=list)

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
