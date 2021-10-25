<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import notifications from '@/store/notifications'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { SavedNetwork, WPANetwork } from '@/types/wifi'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'WifiUpdater',
  async mounted() {
    await callPeriodically(this.fetchSavedNetworks, 5000)
    await callPeriodically(this.fetchNetworkStatus, 5000)
    await callPeriodically(this.fetchAvailableNetworks, 10000)
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
          })
        })
        .catch((error) => {
          wifi.setCurrentNetwork(null)
          if (error === backend_offline_error) { return }
          const message = `Could not fetch wifi status: ${error.message}`
          notifications.pushError({ service: wifi_service, type: 'WIFI_STATUS_FETCH_FAIL', message })
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
          }))
          wifi.setAvailableNetworks(available_networks)
        })
        .catch((error) => {
          wifi.setAvailableNetworks(null)
          if (error === backend_offline_error) { return }
          const message = `Could not scan for wifi networks: ${error.message}`
          notifications.pushError({ service: wifi_service, type: 'WIFI_SCAN_FAIL', message })
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
          notifications.pushError({ service: wifi_service, type: 'WIFI_SAVED_FETCH_FAIL', message })
        })
    },
  },
})
</script>
