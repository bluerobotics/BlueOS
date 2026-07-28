from enum import Enum
from typing import Optional

from pydantic import BaseModel


class HotspotStatus(BaseModel):
    supported: bool
    enabled: bool


class WifiStatus(BaseModel):
    bssid: Optional[str] = None
    freq: Optional[str] = None
    ssid: Optional[str] = None
    id: Optional[str] = None
    mode: Optional[str] = None
    wifi_generation: Optional[str] = None
    pairwise_cipher: Optional[str] = None
    group_cipher: Optional[str] = None
    key_mgmt: Optional[str] = None
    wpa_state: Optional[str] = None
    ip_address: Optional[str] = None
    p2p_device_address: Optional[str] = None
    address: Optional[str] = None
    uuid: Optional[str] = None
    ieee80211ac: Optional[str] = None
    state: Optional[str] = None
    disabled: Optional[str] = None


class ScannedWifiNetwork(BaseModel):
    ssid: Optional[str] = None
    bssid: str
    flags: str
    frequency: int
    signallevel: int


class SavedWifiNetwork(BaseModel):
    networkid: int
    ssid: str
    bssid: Optional[str] = None
    flags: Optional[str] = None
    nm_id: Optional[str] = None
    nm_uuid: Optional[str] = None


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
