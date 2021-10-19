import { Module, Mutation, VuexModule } from 'vuex-module-decorators'

import store from '@/store'
import { Network, SavedNetwork, WifiStatus } from '@/types/wifi'
import { sorted_networks } from '@/utils/wifi'

@Module({
  dynamic: true,
  store,
  name: 'wifi_store',
})

export default class WifiStore extends VuexModule {
  API_URL = '/wifi-manager/v1.0'

  current_network: Network | null = null

  available_networks: Network[] | null = null

  saved_networks: SavedNetwork[] | null = null

  network_status: WifiStatus | null = null

  @Mutation
  setCurrentNetwork(network: Network | null): void {
    this.current_network = network
  }

  @Mutation
  setAvailableNetworks(available_networks: Network[] | null): void {
    this.available_networks = available_networks
  }

  @Mutation
  setSavedNetworks(saved_networks: SavedNetwork[] | null): void {
    this.saved_networks = saved_networks
  }

  @Mutation
  setNetworkStatus(status: WifiStatus | null): void {
    this.network_status = status
  }

  get connectable_networks(): Network[] | null {
    if (this.available_networks === null) {
      return null
    }
    return sorted_networks(this.available_networks.filter((network: Network) => network !== this.current_network))
  }
}
