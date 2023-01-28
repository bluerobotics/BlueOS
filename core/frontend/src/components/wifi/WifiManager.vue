<template>
  <v-card
    elevation="1"
    width="500"
    max-height="80vh"
  >
    <v-app-bar elevate-on-scroll>
      <v-toolbar-title>Wifi</v-toolbar-title>
      <v-spacer />
      <v-btn
        v-tooltip="'Toggle hotspot'"
        icon
        :color="hotspot_status ? 'success' : 'gray'"
        hide-details="auto"
        :loading="hotspot_status_loading"
        @click="toggleHotspot"
      >
        <v-icon>{{ hotspot_status ? 'mdi-access-point' : 'mdi-access-point-off' }}</v-icon>
      </v-btn>
      <v-btn
        v-if="hotspot_status"
        v-tooltip="'WiFi QR Code'"
        icon
        color="primary"
        hide-details="auto"
        @click="toggleQrCodeDialog"
      >
        <v-icon>mdi-qrcode-scan</v-icon>
      </v-btn>
      <v-btn
        v-tooltip="'Settings'"
        icon
        color="gray"
        hide-details="auto"
        @click="toggleSettingsMenu"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </v-app-bar>

    <v-sheet>
      <network-card
        v-if="current_network"
        connected
        :network="current_network"
        :ip-address="wifi_status.ip_address"
        @click="openDisconnectionDialog"
      />

      <v-sheet>
        <div v-if="connectable_networks !== null">
          <div v-if="!connectable_networks.isEmpty()">
            <network-card
              v-for="(network, key) in connectable_networks"
              :key="key"
              class="available-network"
              :network="network"
              @click="openConnectionDialog"
            />
          </div>
          <v-card-text
            v-else
            flat
            class="text-body-1"
          >
            No wifi networks available :(
          </v-card-text>
        </div>
        <div v-else>
          <spinning-logo
            size="30%"
            subtitle="Scanning for wifi networks..."
          />
        </div>
      </v-sheet>
    </v-sheet>

    <connection-dialog
      v-if="selected_network"
      v-model="show_connection_dialog"
      :network="selected_network"
    />

    <disconnection-dialog
      v-if="current_network"
      v-model="show_disconnection_dialog"
      :network="current_network"
      :status="wifi_status"
    />

    <wifi-settings-dialog v-model="show_settings_menu" />

    <v-dialog
      v-model="show_qr_code_dialog"
      width="300"
    >
      <v-card>
        <v-card-title class="text-h5">
          Connect to the hotspot
        </v-card-title>
        <v-card-text>
          <div class="d-flex align-center justify-center">
            <img
              :src="wifi_qr_code_img"
              width="200"
              height="200"
            >
          </div>
          <span>Scan this QR code with your phone to connect to BlueOS's hotspot.</span>
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script lang="ts">
import { uniqBy } from 'lodash'
import Vue from 'vue'
import { generateWifiQRCode } from 'wifi-qr-code-generator'

import Notifier from '@/libs/notifier'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { Network, WifiStatus } from '@/types/wifi'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'
import ConnectionDialog from './ConnectionDialog.vue'
import DisconnectionDialog from './DisconnectionDialog.vue'
import NetworkCard from './NetworkCard.vue'
import WifiSettingsDialog from './WifiSettingsDialog.vue'

const notifier = new Notifier(wifi_service)

export default Vue.extend({
  name: 'WifiManager',
  components: {
    NetworkCard,
    SpinningLogo,
    ConnectionDialog,
    DisconnectionDialog,
    WifiSettingsDialog,
  },
  data() {
    return {
      selected_network: null as Network | null,
      show_connection_dialog: false,
      show_disconnection_dialog: false,
      hotspot_status_loading: false,
      show_settings_menu: false,
      show_qr_code_dialog: false,
      wifi_qr_code_img: '',
    }
  },
  computed: {
    wifi_status(): WifiStatus | null {
      return wifi.network_status
    },
    current_network(): Network | null {
      return wifi.current_network
    },
    connectable_networks(): Network[] | null {
      return uniqBy(wifi.connectable_networks, 'ssid')
    },
    hotspot_status(): boolean | null {
      return wifi.hotspot_status
    },
  },
  watch: {
    hotspot_status(): void {
      this.hotspot_status_loading = false
    },
  },
  methods: {
    openConnectionDialog(network: Network): void {
      this.selected_network = network
      this.show_connection_dialog = true
    },
    openDisconnectionDialog(): void {
      this.show_disconnection_dialog = true
    },
    toggleSettingsMenu(): void {
      this.show_settings_menu = true
    },
    async toggleQrCodeDialog(): Promise<void> {
      await this.updateQrCode()
      this.show_qr_code_dialog = true
    },
    async updateQrCode(): Promise<void> {
      if (wifi.hotspot_credentials === null) { return }
      const qrCodePromise = generateWifiQRCode({
        ssid: wifi.hotspot_credentials.ssid,
        password: wifi.hotspot_credentials.password,
        encryption: 'WPA',
        hiddenSSID: false,
        outputFormat: { type: 'image/png' },
      })
      const data = await qrCodePromise
      console.log(data)
      this.wifi_qr_code_img = data
    },
    async toggleHotspot(): Promise<void> {
      this.hotspot_status_loading = true
      await back_axios({
        method: 'post',
        url: `${wifi.API_URL}/hotspot`,
        params: { enable: !wifi.hotspot_status },
        timeout: 20000,
      })
        .then(() => {
          notifier.pushSuccess('HOTSPOT_STATUS_TOGGLE_SUCCESS', 'Successfully toggled hotspot state.')
        })
        .catch((error) => {
          wifi.setHotspotStatus(null)
          notifier.pushBackError('HOTSPOT_STATUS_TOGGLE_FAIL', error, true)
        })
    },
  },
})
</script>
