import {
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import store from '@/store'
import { NMEASocket } from '@/types/nmea-injector'

@Module({
  dynamic: true,
  store,
  name: 'nmea_injector',
})

class NMEAInjectorStore extends VuexModule {
  API_URL = '/nmea-injector/v1.0'

  available_nmea_sockets: NMEASocket[] = []

  updating_nmea_sockets = true

  @Mutation
  setUpdatingNMEASockets(updating: boolean): void {
    this.updating_nmea_sockets = updating
  }

  @Mutation
  setAvailableNMEASockets(available_nmea_sockets: NMEASocket[]): void {
    this.available_nmea_sockets = available_nmea_sockets
    this.updating_nmea_sockets = false
  }
}

export { NMEAInjectorStore }

const nmea_injector: NMEAInjectorStore = getModule(NMEAInjectorStore)
export default nmea_injector
