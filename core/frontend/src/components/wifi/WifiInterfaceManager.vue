<template>
  <v-card
    elevation="1"
    width="500"
    max-height="80vh"
  >
    <v-app-bar
      elevate-on-scroll
    >
      <v-toolbar-title>
        WiFi - {{ interfaceName }}
      </v-toolbar-title>
      <v-spacer />
      <v-btn
        v-if="is_hotspot_interface"
        v-tooltip="'Hotspot settings'"
        icon
        @click="show_settings_dialog = true"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>
      <v-btn
        v-if="is_hotspot_interface"
        v-tooltip="'Toggle hotspot'"
        icon
        :color="hotspot_status ? 'success' : 'gray'"
        hide-details="auto"
        :loading="hotspot_status_loading"
        :disabled="hotspot_supported === false"
        @click="toggleHotspot"
      >
        <v-icon>{{ hotspot_status ? 'mdi-access-point' : 'mdi-access-point-off' }}</v-icon>
      </v-btn>
    </v-app-bar>

    <wifi-settings-dialog v-model="show_settings_dialog" />

    <v-sheet>
      <v-sheet
        max-height="600"
        class="overflow-y-auto"
      >
        <div v-if="networks !== null && networks.length > 0">
          <v-text-field
            v-if="networks.length > 8"
            v-model="ssid_filter"
            append-icon="mdi-magnify"
            label="Search"
            single-line
            hide-details
            clearable
            class="ml-7 mr-7"
          />
          <wifi-network-card
            v-for="(network, key) in filtered_networks"
            :key="key"
            class="available-network"
            :network="network"
            :connected="isNetworkConnected(network)"
            @click="openConnectionDialog(network)"
          />
        </div>
        <div v-else-if="networks === null">
          <spinning-logo
            size="30%"
            subtitle="Scanning for wifi networks..."
          />
        </div>
        <v-card-text
          v-else
          flat
          class="text-body-1 text-center"
        >
          No wifi networks available :( <br>
          Rescanning...
        </v-card-text>
      </v-sheet>
    </v-sheet>

    <interface-connection-dialog
      v-if="selected_network"
      v-model="show_connection_dialog"
      :network="selected_network"
      :interface-name="interfaceName"
      @connected="onConnected"
      @forget="forgetNetwork"
    />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { Network, WifiInterfaceStatus } from '@/types/wifi'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'
import InterfaceConnectionDialog from './InterfaceConnectionDialog.vue'
import WifiNetworkCard from './WifiNetworkCard.vue'
import WifiSettingsDialog from './WifiSettingsDialog.vue'

const notifier = new Notifier(wifi_service)

export default Vue.extend({
  name: 'WifiInterfaceManager',
  components: {
    WifiNetworkCard,
    SpinningLogo,
    InterfaceConnectionDialog,
    WifiSettingsDialog,
  },
  props: {
    interfaceName: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      selected_network: null as Network | null,
      show_connection_dialog: false,
      show_settings_dialog: false,
      hotspot_status_loading: false,
      ssid_filter: undefined as string | undefined,
    }
  },
  computed: {
    connection_status(): WifiInterfaceStatus | undefined {
      return wifi.interface_status.get(this.interfaceName)
    },
    networks(): Network[] | null {
      const result = wifi.interface_scan_results.get(this.interfaceName)
      if (result === undefined) {
        return null
      }
      return result
    },
    filtered_networks(): Network[] {
      if (!this.networks) return []
      if (!this.ssid_filter || this.ssid_filter.trim() === '') {
        return this.networks
      }
      const filter = this.ssid_filter.toLowerCase()
      return this.networks.filter(
        (network) => network.ssid.toLowerCase().includes(filter),
      )
    },
    is_hotspot_interface(): boolean {
      return this.interfaceName === 'wlan0'
    },
    hotspot_status(): boolean | null {
      return wifi.hotspot_status?.enabled ?? null
    },
    hotspot_supported(): boolean | null {
      return wifi.hotspot_status?.supported ?? null
    },
  },
  methods: {
    isNetworkConnected(network: Network): boolean {
      const status = this.connection_status
      if (!status || status.state !== 'connected') return false
      // Match by BSSID for exact AP identification
      if (status.bssid && network.bssid) {
        return status.bssid.toLowerCase() === network.bssid.toLowerCase()
      }
      // Fallback to SSID only if BSSID not available
      return status.ssid === network.ssid
    },
    openConnectionDialog(network: Network): void {
      this.selected_network = network
      this.show_connection_dialog = true
    },
    onConnected(): void {
      this.show_connection_dialog = false
      notifier.pushSuccess('WIFI_CONNECT_SUCCESS', `Connected to ${this.selected_network?.ssid}`)
    },
    forgetNetwork(network: Network): void {
      wifi.forgettNetwork(network)
    },
    async toggleHotspot(): Promise<void> {
      this.hotspot_status_loading = true
      await back_axios({
        method: 'post',
        url: `${wifi.API_URL}/hotspot`,
        params: { enable: !this.hotspot_status },
        timeout: 20000,
      })
        .then(() => {
          notifier.pushSuccess('HOTSPOT_STATUS_TOGGLE_SUCCESS', 'Successfully toggled hotspot state.')
        })
        .catch((error) => {
          notifier.pushBackError('HOTSPOT_STATUS_TOGGLE_FAIL', error, true)
        })
        .finally(() => {
          this.hotspot_status_loading = false
        })
    },
  },
})
</script>

<style scoped>
</style>
