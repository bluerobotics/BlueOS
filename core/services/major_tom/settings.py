from typing import Any, Dict

from commonwealth.settings import settings
from pykson import ListField, StringField


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    blacklist = ListField(item_type=str)
    # currently supportst blacklisting GPS coordinates
    remote = StringField()

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        if not self.remote:
            self.remote = "http://new.galvanicloop.com:5000"
        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
