<template>
  <v-card
    elevation="1"
    width="500"
    max-height="80vh"
  >
    <v-app-bar
      v-if="showTopBar"
      elevate-on-scroll
    >
      <v-toolbar-title>{{ t`Wifi` }}</v-toolbar-title>
      <v-spacer />
      <v-btn
        v-tooltip="t`Toggle hotspot`"
        icon
        :color="hotspot_status ? 'success' : 'gray'"
        hide-details="auto"
        :loading="hotspot_status_loading"
        :disabled="hotspot_supported === false"
        @click="handleToggleHotspot"
      >
        <v-icon>{{ hotspot_status ? 'mdi-access-point' : 'mdi-access-point-off' }}</v-icon>
      </v-btn>
      <v-btn
        v-if="hotspot_status"
        v-tooltip="t`Hotspot QR code`"
        icon
        color="primary"
        hide-details="auto"
        @click="toggleQrCodeDialog"
      >
        <v-icon>mdi-qrcode-scan</v-icon>
      </v-btn>
      <v-btn
        v-tooltip="t`Settings`"
        icon
        color="gray"
        hide-details="auto"
        @click="toggleSettingsMenu"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </v-app-bar>

    <v-select
      v-if="interfaces.length > 1"
      id="wifi-interface-select"
      :value="selected_interface"
      :items="interface_items"
      :label="t`Wifi interface`"
      prepend-icon="mdi-wifi-cog"
      hide-details
      dense
      class="mx-4 my-3"
      @change="selectInterface"
    >
      <template #item="{ item }">
        <v-icon
          left
          :color="item.connected ? 'success' : undefined"
        >
          {{ item.connected ? 'mdi-wifi-check' : 'mdi-wifi-off' }}
        </v-icon>
        <span>{{ item.value }}</span>
        <span class="ml-2 text--secondary">{{ item.description }}</span>
      </template>
      <template #selection="{ item }">
        <span>{{ item.value }}</span>
        <span class="ml-2 text--secondary">{{ item.description }}</span>
      </template>
    </v-select>

    <v-sheet v-if="!wifi_is_loading">
      <wifi-network-card
        v-if="current_network"
        connected
        :network="current_network"
        :ip-address="wifi_status.ip_address"
        @click="openDisconnectionDialog"
      />

      <v-sheet
        max-height="600"
        class="overflow-y-auto"
      >
        <div v-if="filtered_networks !== null">
          <v-text-field
            v-if="show_search"
            v-model="ssid_filter"
            append-icon="mdi-magnify"
            :label="t`Search`"
            single-line
            hide-details
            clearable
            class="ml-7 mr-7"
          />
          <div v-if="!filtered_networks.isEmpty()">
            <wifi-network-card
              v-for="(network, key) in filtered_networks"
              :key="key"
              class="available-network"
              :network="network"
              @click="openConnectionDialog"
            />
          </div>
          <v-card-text
            v-else
            flat
            class="text-body-1 text-center"
          >
            <template v-if="wifi_status?.state === 'unavailable'">
              {{ t`No wifi adapter` }}
            </template>
            <template v-else>
              {{ t`No wifi networks available :(` }} <br>
              {{ t`Rescanning...` }}
            </template>
          </v-card-text>
        </div>
        <div v-else>
          <spinning-logo
            size="30%"
            :subtitle="t`Scanning for wifi networks...`"
          />
        </div>
      </v-sheet>
    </v-sheet>
    <v-sheet v-else>
      <spinning-logo
        size="30%"
        :subtitle="t`Waiting for wifi networks...`"
      />
    </v-sheet>

    <connection-dialog
      v-if="selected_network"
      v-model="show_connection_dialog"
      :network="selected_network"
      @forget="forgetNetwork"
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
          {{ t`Connect to the hotspot` }}
        </v-card-title>
        <v-card-text>
          <div class="d-flex align-center justify-center">
            <img
              :src="wifi_qr_code_img"
              width="200"
              height="200"
            >
          </div>
          <span>{{ t`Scan this QR code with your phone to connect to BlueOS's hotspot.` }}</span>
        </v-card-text>
      </v-card>
    </v-dialog>

    <WarningDialog
      v-model="show_hotspot_disconnect_warning"
      :message="
        // eslint-disable-next-line max-len
        t`This hotspot is currently being used to access BlueOS. Turning it off could prevent you from accessing your vehicle. Are you sure you want to turn it off?`
      "
      :confirm-label="t`Turn off hotspot`"
      @confirm="toggleHotspot"
    />
  </v-card>
</template>

<script lang="ts">
import { uniqBy } from 'lodash'
import { t } from 'ttag'
import Vue from 'vue'
import { generateWifiQRCode } from 'wifi-qr-code-generator'

import Notifier from '@/libs/notifier'
import beacon from '@/store/beacon'
import wifi from '@/store/wifi'
import { InterfaceType } from '@/types/beacon'
import { wifi_service } from '@/types/frontend_services'
import { Network, WifiStatus } from '@/types/wifi'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'
import WarningDialog from '../common/WarningDialog.vue'
import ConnectionDialog from './ConnectionDialog.vue'
import DisconnectionDialog from './DisconnectionDialog.vue'
import WifiNetworkCard from './WifiNetworkCard.vue'
import WifiSettingsDialog from './WifiSettingsDialog.vue'

const notifier = new Notifier(wifi_service)

export default Vue.extend({
  name: 'WifiManager',
  components: {
    WifiNetworkCard,
    SpinningLogo,
    WarningDialog,
    ConnectionDialog,
    DisconnectionDialog,
    WifiSettingsDialog,
  },
  props: {
    showTopBar: {
      type: Boolean,
      default: true,
    },
  },
  data() {
    return {
      selected_network: null as Network | null,
      show_connection_dialog: false,
      show_disconnection_dialog: false,
      show_hotspot_disconnect_warning: false,
      hotspot_status_loading: false,
      show_settings_menu: false,
      show_qr_code_dialog: false,
      wifi_qr_code_img: '',
      ssid_filter: undefined as string | undefined,
    }
  },
  computed: {
    wifi_is_loading(): boolean {
      return wifi.is_loading
    },
    wifi_status(): WifiStatus | null {
      return wifi.network_status
    },
    interfaces(): string[] {
      return wifi.interfaces
    },
    selected_interface(): string | undefined {
      return wifi.selected_interface ?? wifi.interfaces[0]
    },
    interface_items(): { value: string, connected: boolean, description: string }[] {
      return wifi.interfaces.map((name) => {
        const status = wifi.interface_statuses[name]
        const connected = status?.state === 'connected'
        let description = t`disconnected`
        if (connected) {
          description = status.ssid
        } else if (status === undefined) {
          description = ''
        }
        return { value: name, connected, description }
      })
    },
    current_network(): Network | null {
      this.$emit('current-network', wifi.current_network)
      return wifi.current_network
    },
    connectable_networks(): Network[] | undefined {
      return uniqBy(wifi.connectable_networks, 'ssid')
        // Move known networks to the top
        .sort((a: Network, b: Network) => Number(b.saved) - Number(a.saved))
    },
    filtered_networks(): Network[] | undefined {
      // eslint-disable-next-line eqeqeq
      if (this.ssid_filter == undefined || this.ssid_filter.trim() === '') {
        return this.connectable_networks ?? undefined
      }
      const filter = this.ssid_filter
      return this.connectable_networks?.filter(
        (network) => network.ssid.toLowerCase().includes(filter.toLowerCase()),
      )
    },
    hotspot_status(): boolean | null {
      return wifi.hotspot_status?.enabled ?? null
    },
    hotspot_supported(): boolean | null {
      return wifi.hotspot_status?.supported ?? null
    },
    connected_through_hotspot(): boolean {
      return beacon.available_domains.some(
        (domain) => domain.interface_type === InterfaceType.HOTSPOT
          && domain.ip === beacon.nginx_ip_address,
      )
    },
    show_search(): boolean {
      if (!this.connectable_networks) {
        return false
      }
      return this.connectable_networks.length > 12
    },
  },
  watch: {
    hotspot_status(): void {
      this.hotspot_status_loading = false
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
  },
  methods: {
    selectInterface(selected_interface: string): void {
      wifi.setSelectedInterface(selected_interface)
    },
    forgetNetwork(network: Network): void {
      wifi.forgettNetwork(network)
    },
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
    handleToggleHotspot(): void {
      if (this.hotspot_status && this.connected_through_hotspot) {
        this.show_hotspot_disconnect_warning = true
        return
      }
      this.toggleHotspot()
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
          notifier.pushSuccess('HOTSPOT_STATUS_TOGGLE_SUCCESS', t`Successfully toggled hotspot state.`)
        })
        .catch((error) => {
          notifier.pushBackError('HOTSPOT_STATUS_TOGGLE_FAIL', error, true)
          this.hotspot_status_loading = false
        })
    },
  },
})
</script>
