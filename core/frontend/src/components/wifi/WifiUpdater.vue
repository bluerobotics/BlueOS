<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import {
  Network, SavedNetwork, WifiInterfaceList, WifiInterfaceScanResult, WifiInterfaceStatus, WPANetwork,
} from '@/types/wifi'
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
      // Multi-interface v2 API tasks
      fetch_interfaces_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_interface_scans_task: new OneMoreTime({ delay: 20000, disposeWith: this }),
      fetch_interface_status_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_interface_hotspot_credentials_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  mounted() {
    this.fetch_saved_networks_task.setAction(this.fetchSavedNetworks)
    this.fetch_network_status_task.setAction(this.fetchNetworkStatus)
    this.fetch_hotspot_status_task.setAction(this.fetchHotspotStatus)
    this.fetch_available_networks_task.setAction(this.fetchAvailableNetworks)
    this.fetch_hotspot_credentials_task.setAction(this.fetchHotspotCredentials)
    // Multi-interface v2 API
    this.fetch_interfaces_task.setAction(this.fetchInterfaces)
    this.fetch_interface_scans_task.setAction(this.fetchInterfaceScans)
    this.fetch_interface_status_task.setAction(this.fetchInterfaceStatus)
    this.fetch_interface_hotspot_credentials_task.setAction(this.fetchInterfaceHotspotCredentials)
  },
  methods: {
    async fetchNetworkStatus(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/status`,
        timeout: 10000,
      })
        .then((response) => {
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
          if (isBackendOffline(error)) { return }
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
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/scan`,
        timeout: 20000,
      })
        .then((response) => {
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
          if (isBackendOffline(error)) { return }
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
    async fetchInterfaces(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL_V2}/interfaces/`,
        timeout: 10000,
      })
        .then((response) => {
          const data = response.data as WifiInterfaceList
          wifi.setWifiInterfaces(data.interfaces)
          wifi.setCurrentHotspotInterface(data.hotspot_interface)
        })
        .catch((error) => {
          if (!isBackendOffline(error)) {
            console.debug('v2 interfaces API not available:', error.message)
          }
        })
    },
    async fetchInterfaceScans(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL_V2}/wifi/scan`,
        timeout: 30000,
      })
        .then((response) => {
          const results = response.data as WifiInterfaceScanResult[]
          const saved_networks_ssids = wifi.saved_networks?.map((network: SavedNetwork) => network.ssid) || []

          for (const result of results) {
            const networks: Network[] = result.networks.map((network: WPANetwork) => ({
              ssid: network.ssid,
              signal: network.signallevel,
              locked: network.flags.includes('WPA'),
              saved: saved_networks_ssids.includes(network.ssid),
              bssid: network.bssid,
              frequency: network.frequency,
            }))
            wifi.setInterfaceScanResults({
              interface_name: result.interface,
              networks,
            })
          }
        })
        .catch((error) => {
          if (!isBackendOffline(error)) {
            console.debug('v2 scan API not available:', error.message)
          }
        })
    },
    async fetchInterfaceStatus(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL_V2}/wifi/status`,
        timeout: 10000,
      })
        .then((response) => {
          const results = response.data as WifiInterfaceStatus[]
          for (const status of results) {
            wifi.setInterfaceStatus({
              interface_name: status.interface,
              status,
            })
          }
        })
        .catch((error) => {
          if (!isBackendOffline(error)) {
            console.debug('v2 status API not available:', error.message)
          }
        })
    },
    async fetchInterfaceHotspotCredentials(): Promise<void> {
      for (const iface of wifi.wifi_interfaces) {
        await back_axios({
          method: 'get',
          url: `${wifi.API_URL_V2}/wifi/hotspot/${iface.name}`,
          timeout: 10000,
        })
          .then((response) => {
            const { data } = response
            if (data.ssid && data.password) {
              wifi.setInterfaceHotspotCredentials({
                interface: iface.name,
                credentials: { ssid: data.ssid, password: data.password },
              })
            }
          })
          .catch((error) => {
            // Silently fail - v2 API might not be available
            if (!isBackendOffline(error)) {
              console.debug(`v2 hotspot API not available for ${iface.name}:`, error.message)
            }
          })
      }
    },
  },
})
</script>
