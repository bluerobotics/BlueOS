import {
  Action, getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import store from '@/store'
import { nmea_injector_service } from '@/types/frontend_services'
import { NMEASocket } from '@/types/nmea-injector'
import back_axios from '@/utils/api'

const notifier = new Notifier(nmea_injector_service)

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

  @Action
  async fetchAvailableNMEASockets(): Promise<void> {
    this.setUpdatingNMEASockets(true)
    await back_axios({
      method: 'get',
      url: `${this.API_URL}/socks`,
      timeout: 10000,
    })
      .then((response) => {
        const available_nmea_sockets = response.data
        this.setAvailableNMEASockets(available_nmea_sockets)
      })
      .catch((error) => {
        this.setAvailableNMEASockets([])
        notifier.pushBackError('BRIDGES_FETCH_FAIL', error)
      })
      .finally(() => {
        this.setUpdatingNMEASockets(false)
      })
  }

  @Action
  async removeNMEASocket(socket: NMEASocket): Promise<void> {
    this.setUpdatingNMEASockets(true)
    await back_axios({
      method: 'delete',
      url: `${this.API_URL}/socks`,
      timeout: 10000,
      data: socket,
    })
      .catch((error) => {
        notifier.pushBackError('nmeaSocket_DELETE_FAIL', error)
      })
      .finally(() => {
        this.setUpdatingNMEASockets(false)
      })
  }

  @Action
  async createNMEASocket(socket: NMEASocket): Promise<void> {
    this.setUpdatingNMEASockets(true)
    await back_axios({
      method: 'post',
      url: `${this.API_URL}/socks`,
      timeout: 10000,
      data: socket,
    })
      .catch((error) => {
        notifier.pushBackError('NMEA_SOCKET_CREATE_FAIL', error)
      })
      .finally(() => {
        this.setUpdatingNMEASockets(false)
      })
  }
}

export { NMEAInjectorStore }

const nmea_injector: NMEAInjectorStore = getModule(NMEAInjectorStore)
export default nmea_injector
