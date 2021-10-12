from enum import Enum
from typing import Optional

from pydantic import BaseModel


class ScannedWifiNetwork(BaseModel):
    ssid: Optional[str]
    bssid: str
    flags: str
    frequency: int
    signallevel: int


class SavedWifiNetwork(BaseModel):
    networkid: int
    ssid: str
    bssid: str
    flags: Optional[str]


class WifiCredentials(BaseModel):
    ssid: str
    password: str


class ConnectionStatus(str, Enum):
    JUST_DISCONNECTED = "JUST_DISCONNECTED"
    STILL_DISCONNECTED = "STILL_DISCONNECTED"
    JUST_CONNECTED = "JUST_CONNECTED"
    STILL_CONNECTED = "STILL_CONNECTED"
    UNKNOWN = "UNKNOWN"
