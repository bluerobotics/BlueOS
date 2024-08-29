import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { Bridge } from '@/types/bridges'
import { bridget_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(bridget_service)

let prefetched_bridges = false
let prefetched_serial = false

@Module({
  dynamic: true,
  store,
  name: 'bridget',
})

class BridgetStore extends VuexModule {
  API_URL = '/bridget/v1.0'

  available_bridges: Bridge[] = []

  available_serial_ports: string[] = []

  listener_number = 0

  updating_bridges = true

  updating_serial_ports = true

  fetchAvailableBridgesTask = new OneMoreTime(
    { delay: 5000 },
  )

  fetchAvailableSerialPortsTask = new OneMoreTime(
    { delay: 5000 },
  )

  @Mutation
  setUpdatingBridges(updating: boolean): void {
    this.updating_bridges = updating
  }

  @Mutation
  setUpdatingSerialPorts(updating: boolean): void {
    this.updating_serial_ports = updating
  }

  @Mutation
  setAvailableBridges(available_bridges: Bridge[]): void {
    this.available_bridges = available_bridges
    this.updating_bridges = false
  }

  @Mutation
  setAvailableSerialPorts(available_serial_ports: string[]): void {
    this.available_serial_ports = available_serial_ports
    this.updating_bridges = false
  }

  @Mutation
  registerListener(): void {
    this.listener_number += 1
  }

  @Mutation
  deregisterListener(): void {
    if (this.listener_number <= 0) {
      console.error('Deregister called with zero listeners.')
      return
    }
    this.listener_number -= 1
  }

  @Action
  async fetchAvailableBridges(): Promise<void> {
    if (prefetched_bridges && !this.listener_number) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/bridges`,
      timeout: 10000,
    })
      .then((response) => {
        const available_bridges = response.data
        this.setAvailableBridges(available_bridges)
        prefetched_bridges = true
      })
      .catch((error) => {
        this.setAvailableBridges([])
        notifier.pushBackError('BRIDGES_FETCH_FAIL', error)
      })
      .finally(() => {
        this.setUpdatingBridges(false)
      })
  }

  @Action
  async fetchAvailableSerialPorts(): Promise<void> {
    if (prefetched_serial && !this.listener_number) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/serial_ports`,
      timeout: 10000,
    })
      .then((response) => {
        const available_ports = response.data
        this.setAvailableSerialPorts(available_ports)
        prefetched_serial = true
      })
      .catch((error) => {
        this.setAvailableSerialPorts([])
        notifier.pushBackError('BRIDGET_SERIAL_PORTS_FETCH_FAIL', error)
      })
      .finally(() => {
        this.setUpdatingSerialPorts(false)
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

export { BridgetStore }

const bridget: BridgetStore = getModule(BridgetStore)

bridget.fetchAvailableBridgesTask.setAction(bridget.fetchAvailableBridges)
bridget.fetchAvailableSerialPortsTask.setAction(bridget.fetchAvailableSerialPorts)

export default bridget
