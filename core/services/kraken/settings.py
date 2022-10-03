import json
import re
from typing import Any, Dict

from commonwealth.settings import settings
from pykson import BooleanField, JsonObject, ObjectListField, StringField


class Extension(JsonObject):
    identifier = StringField()
    name = StringField()
    tag = StringField()
    permissions = StringField()
    enabled = BooleanField()

    def settings(self) -> Any:
        return json.loads(self.permissions)

    def fullname(self) -> str:
        return f"{self.name}:{self.tag}"

    def container_name(self) -> str:
        regex = re.compile("[^a-zA-Z0-9]")
        return "extension-" + regex.sub("", f"{self.name}{self.tag}")


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    extensions = ObjectListField(Extension)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
