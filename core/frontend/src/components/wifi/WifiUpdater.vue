<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { SavedNetwork, WifiStatus, WPANetwork } from '@/types/wifi'
import back_axios, { isBackendOffline } from '@/utils/api'

const notifier = new Notifier(wifi_service)

export default Vue.extend({
  name: 'WifiUpdater',
  data() {
    return {
      fetch_saved_networks_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_network_status_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_hotspot_status_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_available_networks_task: new OneMoreTime({ delay: 20000, disposeWith: this }),
      fetch_hotspot_credentials_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_interfaces_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  computed: {
    selected_interface(): string | null {
      return wifi.selected_interface
    },
  },
  watch: {
    selected_interface(): void {
      for (const task of [this.fetch_network_status_task, this.fetch_available_networks_task]) {
        task.stop()
        task.resume()
      }
    },
  },
  mounted() {
    this.fetch_interfaces_task.setAction(this.fetchInterfaces)
    this.fetch_saved_networks_task.setAction(this.fetchSavedNetworks)
    this.fetch_network_status_task.setAction(this.fetchNetworkStatus)
    this.fetch_hotspot_status_task.setAction(this.fetchHotspotStatus)
    this.fetch_available_networks_task.setAction(this.fetchAvailableNetworks)
    this.fetch_hotspot_credentials_task.setAction(this.fetchHotspotCredentials)
  },
  methods: {
    async fetchInterfaces(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/interfaces`,
        timeout: 10000,
      })
        .then(async (response) => {
          const interfaces: string[] = response.data
          wifi.setWifiInterfaces(interfaces)
          // The selected card may have been unplugged
          if (wifi.selected_interface !== null && !interfaces.includes(wifi.selected_interface)) {
            wifi.setSelectedInterface(null)
          }
          await this.fetchInterfaceStatuses(interfaces)
        })
        .catch((error) => {
          wifi.setWifiInterfaces([])
          if (isBackendOffline(error)) { return }
          notifier.pushBackError('WIFI_INTERFACES_FETCH_FAIL', error)
        })
    },
    selectedInterfaceWasRemoved(error: { response?: { status?: number } }, requested: string | null): boolean {
      // A 404 for the selected card means it was unplugged, so go back to the default one without reporting it
      if (requested === null || error.response?.status !== 404) {
        return false
      }
      wifi.setSelectedInterface(null)
      return true
    },
    async fetchInterfaceStatuses(interfaces: string[]): Promise<void> {
      // Only used to describe the cards in the selector, which is only shown with multiple cards
      if (interfaces.length < 2) {
        wifi.setInterfaceStatuses({})
        return
      }
      const statuses: Record<string, WifiStatus> = {}
      await Promise.all(interfaces.map((name) => back_axios({
        method: 'get',
        url: `${wifi.API_URL}/status`,
        params: { interface: name },
        timeout: 10000,
      })
        .then((response) => {
          statuses[name] = response.data
        })
        .catch(() => {
          // The card may be unplugged between listing and querying it
        })))
      wifi.setInterfaceStatuses(statuses)
    },
    async fetchNetworkStatus(): Promise<void> {
      const requested_interface = wifi.selected_interface
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/status`,
        params: wifi.interface_params,
        timeout: 10000,
      })
        .then((response) => {
          // Ignore responses for an interface that is no longer selected
          if (requested_interface !== wifi.selected_interface) { return }
          if (response.data.state === 'unavailable') {
            wifi.setNetworkStatus(response.data)
            wifi.setCurrentNetwork(null)
            wifi.setAvailableNetworks([])
            this.fetch_network_status_task.setDelay(30000)
            return
          }

          this.fetch_network_status_task.setDelay(5000)
          wifi.setNetworkStatus(response.data)

          if (response.data.wpa_state !== 'COMPLETED') {
            wifi.setCurrentNetwork(null)
            return
          }

          const scanned_network = wifi.available_networks?.find((network) => network.ssid === response.data.ssid)
          const saved_network = wifi.saved_networks?.find((network) => network.ssid === response.data.ssid)

          wifi.setCurrentNetwork({
            ssid: response.data.ssid,
            signal: scanned_network ? scanned_network.signal : 0,
            locked: response.data.key_mgmt.includes('WPA'),
            saved: saved_network != null,
            bssid: scanned_network ? scanned_network.bssid : '',
            frequency: scanned_network ? scanned_network.frequency : 0,
          })
        })
        .catch((error) => {
          wifi.setCurrentNetwork(null)
          if (isBackendOffline(error) || this.selectedInterfaceWasRemoved(error, requested_interface)) { return }
          const message = `Could not fetch wifi status: ${error.message}`
          notifier.pushError('WIFI_STATUS_FETCH_FAIL', message)
        })
    },
    async fetchHotspotStatus(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/hotspot_extended_status`,
        timeout: 10000,
      })
        .then((response) => {
          wifi.setHotspotStatus(response.data)
        })
        .catch((error) => {
          wifi.setHotspotStatus(null)
          notifier.pushBackError('HOTSPOT_STATUS_FETCH_FAIL', error)
        })
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/hotspot_interface`,
        timeout: 10000,
      })
        .then((response) => {
          wifi.setHotspotInterface(response.data)
        })
        .catch((error) => {
          wifi.setHotspotInterface(null)
          notifier.pushBackError('HOTSPOT_INTERFACE_FETCH_FAIL', error)
        })
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/smart_hotspot`,
        timeout: 10000,
      })
        .then((response) => {
          wifi.setSmartHotspotStatus(response.data)
        })
        .catch((error) => {
          wifi.setHotspotStatus(null)
          notifier.pushBackError('SMART_HOTSPOT_STATUS_FETCH_FAIL', error)
        })
    },
    async fetchHotspotCredentials(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/hotspot_credentials`,
        timeout: 10000,
      })
        .then((response) => {
          wifi.setHotspotCredentials(response.data)
        })
        .catch((error) => {
          wifi.setHotspotCredentials(null)
          notifier.pushBackError('HOTSPOT_CREDENTIALS_FETCH_FAIL', error)
        })
    },
    async fetchAvailableNetworks(): Promise<void> {
      const requested_interface = wifi.selected_interface
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/scan`,
        params: wifi.interface_params,
        timeout: 20000,
      })
        .then((response) => {
          if (requested_interface !== wifi.selected_interface) { return }
          const saved_networks_ssids = wifi.saved_networks?.map((network: SavedNetwork) => network.ssid)
          const available_networks = response.data.map((network: WPANetwork) => ({
            ssid: network.ssid,
            signal: network.signallevel,
            locked: network.flags.includes('WPA'),
            saved: saved_networks_ssids?.includes(network.ssid) || false,
            bssid: network.bssid,
            frequency: network.frequency,
          }))
          wifi.setAvailableNetworks(available_networks)
        })
        .catch((error) => {
          wifi.setAvailableNetworks(null)
          if (isBackendOffline(error) || this.selectedInterfaceWasRemoved(error, requested_interface)) { return }
          const message = `Could not scan for wifi networks: ${error.message}`
          notifier.pushError('WIFI_SCAN_FAIL', message)
        })
    },
    async fetchSavedNetworks(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/saved`,
        timeout: 10000,
      })
        .then((response) => {
          wifi.setSavedNetworks(response.data)
        })
        .catch((error) => {
          wifi.setSavedNetworks(null)
          if (isBackendOffline(error)) { return }
          const message = `Could not fetch saved networks: ${error.message}.`
          notifier.pushError('WIFI_SAVED_FETCH_FAIL', message)
        })
    },
  },
})
</script>
