import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import {
  Network, NetworkCredentials, SavedNetwork, WifiStatus, HotspotStatus
} from '@/types/wifi'
import { sorted_networks } from '@/utils/wifi'

@Module({
  dynamic: true,
  store,
  name: 'wifi',
})

class WifiStore extends VuexModule {
  API_URL = '/wifi-manager/v1.0'

  current_network: Network | null = null

  available_networks: Network[] | null = null

  saved_networks: SavedNetwork[] | null = null

  network_status: WifiStatus | null = null

  hotspot_status: HotspotStatus | null = null

  hotspot_credentials: NetworkCredentials | null = null

  @Mutation
  setCurrentNetwork(network: Network | null): void {
    this.current_network = network
  }

  @Mutation
  setAvailableNetworks(available_networks: Network[] | null): void {
    this.available_networks = available_networks
  }

  @Mutation
  forgettNetwork(network: Network): void {
    // remove network from saved_networks
    if (this.saved_networks !== null) {
      this.saved_networks = this.saved_networks.filter(
        (saved_network: SavedNetwork) => saved_network.ssid !== network.ssid,
      )
    }
    // find network in available_networks and set saved to false
    if (this.available_networks !== null) {
      const available_networks = this.available_networks.find(
        (available_network: Network) => available_network.ssid === network.ssid,
      )
      if (available_networks) {
        available_networks.saved = false
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
  setHotspotCredentials(credentials: NetworkCredentials | null): void {
    this.hotspot_credentials = credentials
  }

  get connectable_networks(): Network[] | null {
    if (this.available_networks === null) {
      return null
    }
    return sorted_networks(this.available_networks
      .filter((network: Network) => network.ssid !== this.current_network?.ssid))
  }
}

export { WifiStore }

const wifi: WifiStore = getModule(WifiStore)
export default wifi
