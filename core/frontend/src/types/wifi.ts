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
