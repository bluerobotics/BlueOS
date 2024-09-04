from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from controller.platform import Platform, PlatformType


class FlightControllerFlags(str, Enum):
    """Flags for the Flight-controller class."""

    is_bootloader = "is_bootloader"


class FlightController(BaseModel):
    """Flight-controller board."""

    name: str
    manufacturer: Optional[str]
    platform: Platform
    path: Optional[str]
    flags: List[FlightControllerFlags] = []

    @property
    def type(self) -> PlatformType:
        return self.platform.type
