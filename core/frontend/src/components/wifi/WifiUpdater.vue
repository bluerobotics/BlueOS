<template>
  <span />
</template>

<script lang="ts">
import axios, { AxiosResponse } from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationsStore from '@/store/notifications'
import WifiStore from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { SavedNetwork, WPANetwork } from '@/types/wifi'
import { callPeriodically } from '@/utils/helper_functions'

const notification_store: NotificationsStore = getModule(NotificationsStore)
const wifi_store: WifiStore = getModule(WifiStore)

export default Vue.extend({
  name: 'WifiUpdater',
  async mounted() {
    await callPeriodically(this.fetchSavedNetworks, 5000)
    await callPeriodically(this.fetchNetworkStatus, 5000)
    await callPeriodically(this.fetchAvailableNetworks, 10000)
  },
  methods: {
    async fetchNetworkStatus(): Promise<void> {
      await axios({
        method: 'get',
        url: `${wifi_store.API_URL}/status`,
        timeout: 10000,
      })
        .then((response: AxiosResponse) => {
          wifi_store.setNetworkStatus(response.data)

          if (response.data.wpa_state !== 'COMPLETED') {
            wifi_store.setCurrentNetwork(null)
            return
          }

          const scanned_network = wifi_store.available_networks.find((network) => network.ssid === response.data.ssid)
          const saved_network = wifi_store.saved_networks.find((network) => network.ssid === response.data.ssid)

          wifi_store.setCurrentNetwork({
            ssid: response.data.ssid,
            signal: scanned_network ? scanned_network.signal : 0,
            locked: response.data.key_mgmt.includes('WPA'),
            saved: saved_network != null,
          })
        })
        .catch((error) => {
          wifi_store.setCurrentNetwork(null)
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            wifi_service,
            'WIFI_STATUS_FETCH_FAIL',
            `Could not fetch wifi status: ${error.message}`,
          ))
        })
    },
    async fetchAvailableNetworks(): Promise<void> {
      await axios({
        method: 'get',
        url: `${wifi_store.API_URL}/scan`,
        timeout: 20000,
      })
        .then((response) => {
          const saved_networks_ssids = wifi_store.saved_networks.map((network: SavedNetwork) => network.ssid)
          const available_networks = response.data.map((network: WPANetwork) => ({
            ssid: network.ssid,
            signal: network.signallevel,
            locked: network.flags.includes('WPA'),
            saved: saved_networks_ssids.includes(network.ssid),
          }))
          wifi_store.setAvailableNetworks(available_networks)
        })
        .catch((error) => {
          wifi_store.setAvailableNetworks([])
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            wifi_service,
            'WIFI_SCAN_FAIL',
            `Could not scan for wifi networks: ${error.message}`,
          ))
        })
    },
    async fetchSavedNetworks(): Promise<void> {
      await axios({
        method: 'get',
        url: `${wifi_store.API_URL}/saved`,
        timeout: 10000,
      })
        .then((response) => {
          wifi_store.setSavedNetworks(response.data)
        })
        .catch((error) => {
          wifi_store.setSavedNetworks([])
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            wifi_service,
            'WIFI_SAVED_FETCH_FAIL',
            `Could not fetch saved networks: ${error.message}.`,
          ))
        })
    },
  },
})
</script>
