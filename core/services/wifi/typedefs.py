from enum import Enum
from typing import Optional

from pydantic import BaseModel


class HotspotStatus(BaseModel):
    supported: bool
    enabled: bool


class WifiStatus(BaseModel):
    bssid: Optional[str]
    freq: Optional[str]
    ssid: Optional[str]
    id: Optional[str]
    mode: Optional[str]
    wifi_generation: Optional[str]
    pairwise_cipher: Optional[str]
    group_cipher: Optional[str]
    key_mgmt: Optional[str]
    wpa_state: Optional[str]
    ip_address: Optional[str]
    p2p_device_address: Optional[str]
    address: Optional[str]
    uuid: Optional[str]
    ieee80211ac: Optional[str]
    state: Optional[str]
    disabled: Optional[str]


class ScannedWifiNetwork(BaseModel):
    ssid: Optional[str]
    bssid: str
    flags: str
    frequency: int
    signallevel: int


class SavedWifiNetwork(BaseModel):
    networkid: int
    ssid: str
    bssid: Optional[str]
    flags: Optional[str]
    nm_id: Optional[str]


class WifiCredentials(BaseModel):
    ssid: str
    password: str


class ConnectionStatus(str, Enum):
    DISCONNECTING = "DISCONNECTING"
    JUST_DISCONNECTED = "JUST_DISCONNECTED"
    STILL_DISCONNECTED = "STILL_DISCONNECTED"
    CONNECTING = "CONNECTING"
    JUST_CONNECTED = "JUST_CONNECTED"
    STILL_CONNECTED = "STILL_CONNECTED"
    UNKNOWN = "UNKNOWN"
