import { Module, Mutation, VuexModule } from 'vuex-module-decorators'

import store from '@/store'
import { Network, SavedNetwork, WifiStatus } from '@/types/wifi.d'

@Module({
  dynamic: true,
  store,
  name: 'wifi_store',
})

export default class WifiStore extends VuexModule {
  API_URL = '/wifi-manager/v1.0'

  current_network: Network | null = null

  available_networks: Network[] = []

  saved_networks: SavedNetwork[] = []

  network_status: WifiStatus | null = null

  @Mutation
  setCurrentNetwork(network: Network | null): void {
    this.current_network = network
  }

  @Mutation
  setAvailableNetworks(available_networks: Network[]): void {
    this.available_networks = available_networks
  }

  @Mutation
  setSavedNetworks(saved_networks: SavedNetwork[]): void {
    this.saved_networks = saved_networks
  }

  @Mutation
  setNetworkStatus(status: WifiStatus | null): void {
    this.network_status = status
  }
}
