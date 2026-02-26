import axios from 'axios'
import {
  Action,
  getModule, Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import store from '@/store'
import { Domain } from '@/types/beacon'
import { beacon_service } from '@/types/frontend_services'
import back_axios, { isBackendOffline } from '@/utils/api'

interface DiscoveredServices {
  [ip: string]: string[]
}

export interface Vehicle {
  ips: string[]
  hostname: string
  imagePath?: string
}

const notifier = new Notifier(beacon_service)

let prefetched_domains = false
let prefetched_ips = false
let prefetched_names = false

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

  hostname = ''

  vehicle_name = ''

  available_vehicles: Vehicle[] = []

  vehicles_loading = false

  vehicles_error: string | null = null

  fetchAvailableDomainsTask = new OneMoreTime(
    { delay: 5000 },
  )

  fetchIpInfoTask = new OneMoreTime(
    { delay: 5000 },
  )

  fetchVehicleAndHostnameTask = new OneMoreTime(
    { delay: 5000 },
  )

  // eslint-disable-next-line
  @Mutation
  private _setHostname(hostname: string): void {
    this.hostname = hostname
  }

  // eslint-disable-next-line
  @Mutation
  private _setVehicleName(vehicle_name: string): void {
    this.vehicle_name = vehicle_name
  }

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

  @Mutation
  setAvailableVehicles(vehicles: Vehicle[]): void {
    this.available_vehicles = vehicles
  }

  @Mutation
  setVehiclesLoading(loading: boolean): void {
    this.vehicles_loading = loading
  }

  @Mutation
  setVehiclesError(error: string | null): void {
    this.vehicles_error = error
  }

  @Action
  async setHostname(hostname: string): Promise<boolean> {
    hostname = hostname.trim().toLowerCase()
    const regex = /^[a-zA-Z0-9-]+$/
    if (!regex.test(hostname)) {
      const message = 'Could not set hostname: invalid string, '
        + 'it should contain only alpha-numeric and \'-\' characters.'
      notifier.pushError('BEACON_SET_HOSTNAME_FAIL', message, true)
      return false
    }

    return back_axios({
      method: 'post',
      url: `${this.API_URL}/hostname`,
      timeout: 5000,
      params: {
        hostname: `${hostname}`,
      },
    })
      .then(() => {
        // eslint-disable-next-line
        this._setHostname(hostname)
        return true
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return false
        }
        const message = `Could not set hostname: ${error.message ?? error.response?.data}.`
        notifier.pushError('BEACON_SET_HOSTNAME_FAIL', message, true)
        return false
      })
  }

  @Action
  async setVehicleName(vehicle_name: string): Promise<boolean> {
    return back_axios({
      method: 'post',
      url: `${this.API_URL}/vehicle_name`,
      timeout: 5000,
      params: {
        name: vehicle_name,
      },
    })
      .then(() => {
        // eslint-disable-next-line
        this._setVehicleName(vehicle_name)
        return true
      })
      .catch((error) => {
        if (isBackendOffline(error)) {
          return false
        }
        const message = `Could not set vehicle name: ${error.response?.data ?? error.message}.`
        notifier.pushError('BEACON_SET_VEHICLE_NAME_FAIL', message, true)
        return false
      })
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
  async fetchVehicleAndHostname(): Promise<void> {
    if (prefetched_names && !this.listeners_count) {
      return
    }

    if (this.hostname === '') {
      back_axios({
        method: 'get',
        url: `${this.API_URL}/hostname`,
        timeout: 5000,
      })
        .then((response) => {
          // eslint-disable-next-line
          this._setHostname(response.data)
        })
        .catch((error) => {
          notifier.pushBackError('BEACON_HOSTNAME_FETCH_FAIL', error)
        })
    }

    if (this.vehicle_name === '') {
      back_axios({
        method: 'get',
        url: `${this.API_URL}/vehicle_name`,
        timeout: 5000,
      })
        .then((response) => {
          // eslint-disable-next-line
          this._setVehicleName(response.data)
        })
        .catch((error) => {
          notifier.pushBackError('BEACON_VEHICLE_NAME_FETCH_FAIL', error)
        })
    }

    if (this.hostname !== undefined && this.vehicle_name !== '') {
      prefetched_names = true
    }
  }

  @Action
  async fetchDiscoveredServices(): Promise<void> {
    this.setVehiclesLoading(true)
    this.setVehiclesError(null)
    this.setAvailableVehicles([])

    try {
      const response = await back_axios({
        method: 'get',
        url: `${this.API_URL}/discovered_services`,
        timeout: 10000,
      })

      const discoveredServices: DiscoveredServices = response.data
      const ips = Object.keys(discoveredServices)

      if (ips.length === 0) {
        this.setVehiclesError('No vehicles discovered')
        this.setVehiclesLoading(false)
        return
      }

      const vehicles: Vehicle[] = []

      await Promise.all(ips.map(async (ip) => {
        try {
          const hostnameResponse = await axios.get(`http://${ip}/beacon/v1.0/hostname`, {
            timeout: 5000,
          })

          let imagePath: string | undefined
          try {
            const imageResponse = await axios.get(`http://${ip}/bag/v1.0/get/vehicle.image_path`, {
              timeout: 3000,
            })
            imagePath = `http://${ip}${imageResponse.data.url}`
          } catch {
            // Image not available, use fallback
          }

          vehicles.push({
            ips: [ip],
            hostname: hostnameResponse.data,
            imagePath,
          })
        } catch (error) {
          console.warn(`Failed to fetch hostname for ${ip}:`, error)
        }
      }))

      vehicles.sort((a, b) => a.hostname.localeCompare(b.hostname))
      this.setAvailableVehicles(vehicles)

      if (vehicles.length === 0) {
        this.setVehiclesError('No accessible vehicles found')
      }
    } catch (error) {
      console.error('Failed to fetch discovered services:', error)
      this.setVehiclesError('Failed to discover vehicles')
      this.setAvailableVehicles([])
    } finally {
      this.setVehiclesLoading(false)
    }
  }

  @Action
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

beacon.fetchAvailableDomainsTask.setAction(beacon.fetchAvailableDomains)
beacon.fetchIpInfoTask.setAction(beacon.fetchIpInfo)
beacon.fetchVehicleAndHostnameTask.setAction(beacon.fetchVehicleAndHostname)

export default beacon
