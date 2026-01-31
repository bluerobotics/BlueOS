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
      <!-- Mode selector -->
      <v-menu
        v-if="supports_mode_switching"
        offset-y
      >
        <template #activator="{ on, attrs }">
          <v-btn
            v-tooltip="'Interface mode'"
            text
            small
            v-bind="attrs"
            :loading="mode_loading"
            v-on="on"
          >
            <v-icon left small>
              {{ mode_icon }}
            </v-icon>
            {{ mode_label }}
            <v-icon right small>
              mdi-chevron-down
            </v-icon>
          </v-btn>
        </template>
        <v-list dense>
          <v-list-item
            v-for="mode in available_modes"
            :key="mode"
            :disabled="mode === current_mode"
            @click="setInterfaceMode(mode)"
          >
            <v-list-item-icon>
              <v-icon small>
                {{ getModeIcon(mode) }}
              </v-icon>
            </v-list-item-icon>
            <v-list-item-title>{{ getModeLabel(mode) }}</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
      <!-- Hotspot settings button - shown when not in client-only mode -->
      <v-btn
        v-if="current_mode !== WifiInterfaceMode.NORMAL"
        v-tooltip="'Hotspot settings'"
        icon
        @click="show_settings_dialog = true"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </v-app-bar>

    <wifi-settings-dialog v-model="show_settings_dialog" />

    <v-sheet>
      <v-sheet
        max-height="600"
        class="overflow-y-auto"
      >
        <!-- Hotspot-only mode: Show hotspot info instead of scan results -->
        <div v-if="current_mode === WifiInterfaceMode.HOTSPOT">
          <v-card-text class="text-center pa-8">
            <v-icon
              size="64"
              color="success"
              class="mb-4"
            >
              mdi-access-point
            </v-icon>
            <div class="text-h6 mb-2">
              Hotspot Mode Active
            </div>
            <div class="text-body-2 grey--text">
              This interface is running as an access point.<br>
              Use the settings button to configure SSID and password.
            </div>
          </v-card-text>
        </div>
        <!-- Client or Dual mode: Show network scan results -->
        <div v-else-if="networks !== null && networks.length > 0">
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
import {
  Network,
  WifiInterfaceCapabilities,
  WifiInterfaceMode,
  WifiInterfaceStatus,
} from '@/types/wifi'
import back_axios, { isBackendOffline } from '@/utils/api'

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
      ssid_filter: undefined as string | undefined,
      interface_capabilities: null as WifiInterfaceCapabilities | null,
      mode_loading: false,
      WifiInterfaceMode,
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
    current_mode(): WifiInterfaceMode {
      return this.interface_capabilities?.current_mode ?? WifiInterfaceMode.NORMAL
    },
    available_modes(): WifiInterfaceMode[] {
      return this.interface_capabilities?.available_modes ?? [WifiInterfaceMode.NORMAL]
    },
    supports_mode_switching(): boolean {
      return this.available_modes.length > 1
    },
    mode_label(): string {
      const labels: Record<WifiInterfaceMode, string> = {
        [WifiInterfaceMode.NORMAL]: 'Client',
        [WifiInterfaceMode.HOTSPOT]: 'Hotspot',
        [WifiInterfaceMode.DUAL]: 'Dual',
      }
      return labels[this.current_mode] || 'Client'
    },
    mode_icon(): string {
      const icons: Record<WifiInterfaceMode, string> = {
        [WifiInterfaceMode.NORMAL]: 'mdi-wifi',
        [WifiInterfaceMode.HOTSPOT]: 'mdi-access-point',
        [WifiInterfaceMode.DUAL]: 'mdi-wifi-plus',
      }
      return icons[this.current_mode] || 'mdi-wifi'
    },
  },
  mounted() {
    this.fetchInterfaceCapabilities()
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
    async fetchInterfaceCapabilities(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL_V2}/wifi/mode/${this.interfaceName}`,
        timeout: 10000,
      })
        .then((response) => {
          this.interface_capabilities = response.data
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          // Fallback - assume normal mode only
          this.interface_capabilities = {
            interface: this.interfaceName,
            supports_ap_mode: false,
            supports_dual_mode: false,
            current_mode: WifiInterfaceMode.NORMAL,
            available_modes: [WifiInterfaceMode.NORMAL],
          }
        })
    },
    getModeIcon(mode: WifiInterfaceMode): string {
      const icons: Record<WifiInterfaceMode, string> = {
        [WifiInterfaceMode.NORMAL]: 'mdi-wifi',
        [WifiInterfaceMode.HOTSPOT]: 'mdi-access-point',
        [WifiInterfaceMode.DUAL]: 'mdi-wifi-plus',
      }
      return icons[mode] || 'mdi-wifi'
    },
    getModeLabel(mode: WifiInterfaceMode): string {
      const labels: Record<WifiInterfaceMode, string> = {
        [WifiInterfaceMode.NORMAL]: 'Client Only',
        [WifiInterfaceMode.HOTSPOT]: 'Hotspot Only',
        [WifiInterfaceMode.DUAL]: 'Dual (Client + Hotspot)',
      }
      return labels[mode] || 'Client Only'
    },
    async setInterfaceMode(mode: WifiInterfaceMode): Promise<void> {
      if (mode === this.current_mode) return

      this.mode_loading = true
      await back_axios({
        method: 'post',
        url: `${wifi.API_URL_V2}/wifi/mode`,
        data: { interface: this.interfaceName, mode },
        timeout: 30000,
      })
        .then(() => {
          const labels: Record<WifiInterfaceMode, string> = {
            [WifiInterfaceMode.NORMAL]: 'Client',
            [WifiInterfaceMode.HOTSPOT]: 'Hotspot',
            [WifiInterfaceMode.DUAL]: 'Dual',
          }
          notifier.pushSuccess('MODE_CHANGE_SUCCESS', `${this.interfaceName} switched to ${labels[mode]} mode.`)
          this.fetchInterfaceCapabilities()
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          notifier.pushBackError('MODE_CHANGE_FAIL', error, true)
        })
        .finally(() => {
          this.mode_loading = false
        })
    },
  },
})
</script>

<style scoped>
</style>
