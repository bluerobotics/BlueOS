import json
import re
from typing import Any, Dict

from commonwealth.settings import settings
from pykson import BooleanField, JsonObject, ObjectListField, StringField, IntegerField


class ExtensionSettings(JsonObject):
    identifier = StringField()
    name = StringField()
    docker = StringField()
    tag = StringField()
    permissions = StringField()
    enabled = BooleanField()
    user_permissions = StringField()

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

class ManifestSettings(JsonObject):
    identifier = StringField()
    priority = IntegerField()
    name = StringField()
    url = StringField()

class SettingsV1(settings.BaseSettings):
    VERSION = 1
    extensions = ObjectListField(ExtensionSettings)
    manifests = ObjectListField(ManifestSettings)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
