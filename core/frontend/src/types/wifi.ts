export interface Network {
    ssid: string
    signal: number
    locked: boolean
    saved: boolean
    bssid: string
    frequency: number
}

export interface HotspotStatus {
    enabled: boolean
    supported: boolean
}

export interface WifiStatus {
    bssid: string
    freq: number
    ssid: string
    id: number
    mode: string
    wifi_generation: number
    pairwise_cipher: string
    group_cipher: string
    key_mgmt: string
    wpa_state: string
    ip_address: string
    p2p_device_address: string
    address: string
    uuid: string
}

export interface WPANetwork {
    ssid: string
    bssid: string
    flags: string
    frequency: number
    signallevel: number
}

export interface SavedNetwork {
    networkid: number
    ssid: string
    bssid: string
    flags: string
}

export interface NetworkCredentials {
    ssid: string
    password: string
}

// API v2 types for multi-interface support

export enum WifiInterfaceMode {
    NORMAL = 'normal',
    HOTSPOT = 'hotspot',
    DUAL = 'dual',
}

export interface WifiInterface {
    name: string
    connected: boolean
    ssid: string | null
    signal_strength: number | null
    ip_address: string | null
    mac_address: string | null
    mode: WifiInterfaceMode
    supports_hotspot: boolean
    supports_dual_mode: boolean
}

export interface WifiInterfaceList {
    interfaces: WifiInterface[]
    hotspot_interface: string | null
}

export interface WifiInterfaceStatus {
    interface: string
    state: string
    ssid: string | null
    bssid: string | null
    ip_address: string | null
    signal_strength: number | null
    frequency: number | null
    key_mgmt: string | null
}

export interface WifiInterfaceScanResult {
    interface: string
    networks: WPANetwork[]
}

export interface ConnectRequest {
    interface: string
    credentials: NetworkCredentials
    hidden: boolean
}

export interface DisconnectRequest {
    interface: string
}

export interface HotspotRequest {
    interface: string
}

export interface HotspotCredentialsRequest {
    interface: string
    credentials: NetworkCredentials
}

export interface InterfaceHotspotStatus {
    interface: string
    supported: boolean
    enabled: boolean
    ssid: string | null
    password: string | null
}

export interface WifiInterfaceCapabilities {
    interface: string
    supports_ap_mode: boolean
    supports_dual_mode: boolean
    current_mode: WifiInterfaceMode
    available_modes: WifiInterfaceMode[]
}

export interface SetInterfaceModeRequest {
    interface: string
    mode: WifiInterfaceMode
}
