import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { ping_service } from '@/types/frontend_services'
import { PingDevice } from '@/types/ping'
import back_axios from '@/utils/api'

const notifier = new Notifier(ping_service)

let prefecthed_pings = false

@Module({
  dynamic: true,
  store,
  name: 'ping',
})

class PingStore extends VuexModule {
  API_URL = '/ping/v1.0'

  available_ping_devices: PingDevice[] = []

  ping_listeners_number = 0

  updating_ping_devices = true

  fetchAvailablePingDevicesTask = new OneMoreTime(
    { delay: 5000 },
  )

  @Mutation
  setAvailablePingDevices(available_ping_devices: PingDevice[]): void {
    this.available_ping_devices = available_ping_devices
    this.updating_ping_devices = false
  }

  @Mutation
  registerListener(): void {
    this.ping_listeners_number += 1
  }

  @Mutation
  deregisterListener(): void {
    if (this.ping_listeners_number <= 0) {
      console.error('Deregister called with zero listeners.')
      return
    }
    this.ping_listeners_number -= 1
  }

  @Action
  async fetchAvailablePingDevices(): Promise<void> {
    if (prefecthed_pings && !this.ping_listeners_number) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/sensors`,
      timeout: 10000,
    })
      .then((response) => {
        const available_pings = response.data
        this.setAvailablePingDevices(available_pings)
        prefecthed_pings = true
      })
      .catch((error) => {
        this.setAvailablePingDevices([])
        notifier.pushBackError('PING_FETCH_FAIL', error)
      })
  }

  @Action
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  async registerObject(object: any): Promise<void> {
    this.registerListener()
    const ref = new WeakRef(object)
    const id = setInterval(() => {
      // Check if object does not exist anymore or if it was destroyed by vue
      // eslint-disable-next-line
      if (!ref.deref() || ref.deref()._isDestroyed) {
        this.deregisterListener()
        clearInterval(id)
      }
    }, 1000)
  }
}

export { PingStore }

const ping: PingStore = getModule(PingStore)

ping.fetchAvailablePingDevicesTask.setAction(ping.fetchAvailablePingDevices)

export default ping
