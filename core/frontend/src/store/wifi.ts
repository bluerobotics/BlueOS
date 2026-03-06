import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import {
  HotspotStatus,
  Network,
  NetworkCredentials,
  SavedNetwork,
  WifiInterface,
  WifiInterfaceStatus,
  WifiStatus,
} from '@/types/wifi'
import { sorted_networks } from '@/utils/wifi'

@Module({
  dynamic: true,
  store,
  name: 'wifi',
})

class WifiStore extends VuexModule {
  API_URL = '/wifi-manager/v1.0'

  API_URL_V2 = '/wifi-manager/v2.0'

  current_network: Network | null = null

  available_networks: Network[] | null = null

  saved_networks: SavedNetwork[] | null = null

  network_status: WifiStatus | null = null

  hotspot_status: HotspotStatus | null = null

  smart_hotspot_status: boolean | null = null

  hotspot_credentials: NetworkCredentials | null = null

  is_loading = true

  // Multi-interface support (v2 API)
  wifi_interfaces: WifiInterface[] = []

  interface_scan_results: Map<string, Network[]> = new Map()

  interface_status: Map<string, WifiInterfaceStatus> = new Map()

  interface_hotspot_credentials: Map<string, NetworkCredentials> = new Map()

  current_hotspot_interface: string | null = null

  @Mutation
  setCurrentNetwork(network: Network | null): void {
    this.current_network = network
  }

  @Mutation
  setAvailableNetworks(available_networks: Network[] | null): void {
    this.is_loading = false
    this.available_networks = available_networks
  }

  @Mutation
  forgettNetwork(network: Network): void {
    if (this.saved_networks !== null) {
      this.saved_networks = this.saved_networks.filter(
        (saved_network: SavedNetwork) => saved_network.ssid !== network.ssid,
      )
    }
    if (this.available_networks !== null) {
      const available_network = this.available_networks.find(
        (n: Network) => n.ssid === network.ssid,
      )
      if (available_network) {
        available_network.saved = false
      }
    }
  }

  @Mutation
  setSavedNetworks(saved_networks: SavedNetwork[] | null): void {
    this.saved_networks = saved_networks
  }

  @Mutation
  setNetworkStatus(status: WifiStatus | null): void {
    this.network_status = status
  }

  @Mutation
  setHotspotStatus(status: HotspotStatus | null): void {
    this.hotspot_status = status
  }

  @Mutation
  setSmartHotspotStatus(status: boolean | null): void {
    this.smart_hotspot_status = status
  }

  @Mutation
  setHotspotCredentials(credentials: NetworkCredentials | null): void {
    this.hotspot_credentials = credentials
  }

  @Mutation
  setInterfaceHotspotCredentials(payload: { interface: string; credentials: NetworkCredentials }): void {
    this.interface_hotspot_credentials = new Map(this.interface_hotspot_credentials)
    this.interface_hotspot_credentials.set(payload.interface, payload.credentials)
  }

  @Mutation
  setLoading(loading: boolean): void {
    this.is_loading = loading
  }

  // Multi-interface mutations

  @Mutation
  setWifiInterfaces(interfaces: WifiInterface[]): void {
    this.wifi_interfaces = interfaces
  }

  @Mutation
  setInterfaceScanResults(payload: { interface_name: string; networks: Network[] }): void {
    this.interface_scan_results = new Map(this.interface_scan_results)
    this.interface_scan_results.set(payload.interface_name, payload.networks)
  }

  @Mutation
  setInterfaceStatus(payload: { interface_name: string; status: WifiInterfaceStatus }): void {
    this.interface_status = new Map(this.interface_status)
    this.interface_status.set(payload.interface_name, payload.status)
  }

  @Mutation
  setCurrentHotspotInterface(interface_name: string | null): void {
    this.current_hotspot_interface = interface_name
  }

  get connectable_networks(): Network[] | null {
    if (this.available_networks === null) {
      return null
    }
    return sorted_networks(this.available_networks
      .filter((network: Network) => network.ssid !== this.current_network?.ssid))
  }

  getInterface(name: string): WifiInterface | undefined {
    return this.wifi_interfaces.find((iface) => iface.name === name)
  }

  getInterfaceNetworks(name: string): Network[] {
    return this.interface_scan_results.get(name) ?? []
  }

  getInterfaceConnectionStatus(name: string): WifiInterfaceStatus | undefined {
    return this.interface_status.get(name)
  }
}

export { WifiStore }

const wifi: WifiStore = getModule(WifiStore)
export default wifi
