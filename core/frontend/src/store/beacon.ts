import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import store from '@/store'
import { Domain } from '@/types/beacon'
import { beacon_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

const notifier = new Notifier(beacon_service)

let prefetched_domains = false
let prefetched_ips = false

@Module({
  dynamic: true,
  store,
  name: 'beacon',
})

class BeaconStore extends VuexModule {
  API_URL = '/beacon/v1.0'

  available_domains: Domain[] = []

  listeners_count = 0

  client_ip_address = ''

  nginx_ip_address = ''

  @Mutation
  setAvailableDomains(domains: Domain[]): void {
    this.available_domains = domains
  }

  @Mutation
  setClientIpAddress(ip: string): void {
    this.client_ip_address = ip
  }

  @Mutation
  setNginxIpAddress(ip: string): void {
    this.nginx_ip_address = ip
  }

  @Mutation
  addListener(): void {
    this.listeners_count += 1
  }

  @Mutation
  removeListener(): void {
    if (this.listeners_count <= 0) {
      console.error('Deregister called with zero listeners.')
      return
    }
    this.listeners_count -= 1
  }

  @Action
  async fetchAvailableDomains(): Promise<void> {
    if (prefetched_domains && !this.listeners_count) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/services`,
      timeout: 10000,
    })
      .then((response) => {
        const available_domains = response.data
        this.setAvailableDomains(available_domains)
        prefetched_domains = true
      })
      .catch((error) => {
        this.setAvailableDomains([])
        notifier.pushBackError('BEACON_DOMAINS_FETCH_FAIL', error)
      })
  }

  @Action
  async fetchIpInfo(): Promise<void> {
    if (prefetched_ips && !this.listeners_count) {
      return
    }
    back_axios({
      method: 'get',
      url: `${this.API_URL}/ip`,
      timeout: 10000,
    })
      .then((response) => {
        const ip_info = response.data
        this.setClientIpAddress(ip_info.client_ip)
        this.setNginxIpAddress(ip_info.interface_ip)
        prefetched_ips = true
      })
      .catch((error) => {
        this.setClientIpAddress('')
        this.setNginxIpAddress('')
        notifier.pushBackError('BEACON_IP_FETCH_FAIL', error)
      })
  }

  @Action
  async registerBeaconListener(object: any): Promise<void> {
    this.addListener()
    const ref = new WeakRef(object)
    const id = setInterval(() => {
      // Check if object does not exist anymore or if it was destroyed by vue
      // eslint-disable-next-line
      if (!ref.deref() || ref.deref()._isDestroyed) {
        this.removeListener()
        clearInterval(id)
      }
    }, 1000)
  }
}

export { BeaconStore }

const beacon: BeaconStore = getModule(BeaconStore)
callPeriodically(beacon.fetchAvailableDomains, 5000)
callPeriodically(beacon.fetchIpInfo, 5000)
export default beacon
