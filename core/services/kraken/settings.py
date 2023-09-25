import json
import re
from typing import Any, Dict

from commonwealth.settings import settings
from pykson import BooleanField, JsonObject, ListField, ObjectListField, StringField

GITHUB_URL = "https://bluerobotics.github.io/BlueOS-Extensions-Repository/manifest.json"
BAZAAR_URL = "https://app.blueos.cloud/api/agent/bazaar/manifest/"


class Extension(JsonObject):
    identifier = StringField()
    name = StringField()
    docker = StringField()
    tag = StringField()
    permissions = StringField()
    enabled = BooleanField()
    user_permissions = StringField()
    id = StringField(null=True)

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


class SettingsV2(SettingsV1):
    VERSION = 2
    manifest_urls = ListField(StringField())

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        self.VERSION = SettingsV2.VERSION
        # this shold run in migrate() but migrate is never called ???
        if len(self.manifest_urls) == 0:
            self.manifest_urls.append(GITHUB_URL)

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.VERSION:
            return

        if data["VERSION"] < SettingsV2.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV2.VERSION
