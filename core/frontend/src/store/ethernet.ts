import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { EthernetInterface } from '@/types/ethernet'

@Module({
  dynamic: true,
  store,
  name: 'ethernet',
})

class EthernetStore extends VuexModule {
  API_URL = '/cable-guy/v1.0'

  available_interfaces: EthernetInterface[] = []

  updating_interfaces = true

  @Mutation
  setUpdatingInterfaces(updating: boolean): void {
    this.updating_interfaces = updating
  }

  @Mutation
  setInterfaces(ethernet_interfaces: EthernetInterface[]): void {
    this.available_interfaces = ethernet_interfaces
    this.updating_interfaces = false
  }
}

export { EthernetStore }

const ethernet: EthernetStore = getModule(EthernetStore)
export default ethernet
