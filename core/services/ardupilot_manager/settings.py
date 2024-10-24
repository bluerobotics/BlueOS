from typing import Any, Dict, Optional

from commonwealth.settings.bases.pydantic_base import PydanticSettings


class SettingsV1(PydanticSettings):
    sitl_frame: Optional[str] = None
    prefered_router: Optional[str] = None

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
        data["animal"] = self.animal
        data["first_variable"] = self.first_variable
