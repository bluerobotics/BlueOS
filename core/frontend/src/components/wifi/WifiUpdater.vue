<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { SavedNetwork, WPANetwork } from '@/types/wifi'
import back_axios, { backend_offline_error } from '@/utils/api'

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
    }
  },
  mounted() {
    this.fetch_saved_networks_task.setAction(this.fetchSavedNetworks)
    this.fetch_network_status_task.setAction(this.fetchNetworkStatus)
    this.fetch_hotspot_status_task.setAction(this.fetchHotspotStatus)
    this.fetch_available_networks_task.setAction(this.fetchAvailableNetworks)
    this.fetch_hotspot_credentials_task.setAction(this.fetchHotspotCredentials)
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
          if (error === backend_offline_error) { return }
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
          if (error === backend_offline_error) { return }
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
          if (error === backend_offline_error) { return }
          const message = `Could not fetch saved networks: ${error.message}.`
          notifier.pushError('WIFI_SAVED_FETCH_FAIL', message)
        })
    },
  },
})
</script>
