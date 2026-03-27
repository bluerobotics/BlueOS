import json
import re
from typing import Any, Dict, Sequence

from commonwealth.settings.settings import PydanticSettings
from pydantic import BaseModel, Field


class ExtensionSettings(BaseModel):
    identifier: str
    name: str
    docker: str
    tag: str
    permissions: str
    enabled: bool
    user_permissions: str

    def settings(self) -> Any:
        if self.user_permissions:
            return json.loads(self.user_permissions)
        return json.loads(self.permissions)

    def is_valid(self) -> bool:
        if not self.docker:
            return False
        return True

    def fullname(self) -> str:
        return f"{self.docker}:{self.tag}"

    def container_name(self) -> str:
        regex = re.compile("[^a-zA-Z0-9]")
        return "extension-" + regex.sub("", f"{self.docker}{self.tag}")


class ManifestSettings(BaseModel):
    identifier: str
    enabled: bool
    priority: int
    factory: bool
    name: str
    url: str


class SettingsV1(PydanticSettings):
    extensions: Sequence[ExtensionSettings] = Field(default_factory=list)

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION


class SettingsV2(SettingsV1):
    manifests: Sequence[ManifestSettings] = Field(default_factory=list)

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV2.STATIC_VERSION:
            super().migrate(data)

            data["VERSION"] = SettingsV2.STATIC_VERSION
            data["manifests"] = []
