from enum import Enum
from typing import List, Optional

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
    nm_uuid: Optional[str]


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


class WifiInterfaceMode(str, Enum):
    """Operating mode for a WiFi interface."""

    NORMAL = "normal"  # Client mode only - connect to networks
    HOTSPOT = "hotspot"  # AP mode only - become an access point
    DUAL = "dual"  # Both simultaneously (requires hardware support)


# API v2 models for multi-interface support


class WifiInterface(BaseModel):
    """Represents a WiFi interface on the system."""

    name: str
    connected: bool
    ssid: Optional[str]
    signal_strength: Optional[int]
    ip_address: Optional[str]
    mac_address: Optional[str]
    mode: WifiInterfaceMode = WifiInterfaceMode.NORMAL
    supports_hotspot: bool = False
    supports_dual_mode: bool = False


class WifiInterfaceStatus(BaseModel):
    """Extended status for a specific WiFi interface."""

    interface: str
    state: str
    ssid: Optional[str]
    bssid: Optional[str]
    ip_address: Optional[str]
    signal_strength: Optional[int]
    frequency: Optional[int]
    key_mgmt: Optional[str]


class WifiInterfaceScanResult(BaseModel):
    """Scan results for a specific interface."""

    interface: str
    networks: List[ScannedWifiNetwork]


class ConnectRequest(BaseModel):
    """Request to connect to a network on a specific interface."""

    interface: str
    credentials: WifiCredentials
    hidden: bool = False


class DisconnectRequest(BaseModel):
    """Request to disconnect a specific interface."""

    interface: str


class HotspotRequest(BaseModel):
    """Request to start/stop hotspot on a specific interface."""

    interface: str


class HotspotCredentialsRequest(BaseModel):
    """Request to update hotspot credentials for a specific interface."""

    interface: str
    credentials: WifiCredentials


class InterfaceHotspotStatus(BaseModel):
    """Hotspot status for a specific interface."""

    interface: str
    supported: bool
    enabled: bool
    ssid: Optional[str]
    password: Optional[str]


class WifiInterfaceList(BaseModel):
    """List of available WiFi interfaces."""

    interfaces: List[WifiInterface]
    hotspot_interface: Optional[str] = None


class WifiInterfaceCapabilities(BaseModel):
    """Hardware capabilities of a WiFi interface."""

    interface: str
    supports_ap_mode: bool
    supports_dual_mode: bool  # Can run AP + managed simultaneously
    current_mode: WifiInterfaceMode
    available_modes: List[WifiInterfaceMode]


class SetInterfaceModeRequest(BaseModel):
    """Request to set interface operating mode."""

    interface: str
    mode: WifiInterfaceMode
