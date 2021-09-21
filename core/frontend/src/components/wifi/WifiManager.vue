<template>
  <v-card
    elevation="1"
    width="500"
  >
    <v-container>
      <v-container v-if="current_network">
        <network-card
          class="connected-network"
          :network="current_network"
          @click="openDisconnectionDialog"
        />
      </v-container>

      <v-container v-if="are_connectable_networks_available">
        <network-card
          v-for="(network, key) in connectable_networks"
          :key="key"
          class="available-network"
          :network="network"
          @click="openConnectionDialog"
        />
      </v-container>
      <v-container v-else>
        <spinning-logo size="30%" />
      </v-container>
    </v-container>
    <wifi-updater />

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
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import WifiStore from '@/store/wifi'
import { Network, WifiStatus } from '@/types/wifi.d'

import SpinningLogo from '../common/SpinningLogo.vue'
import ConnectionDialog from './ConnectionDialog.vue'
import DisconnectionDialog from './DisconnectionDialog.vue'
import NetworkCard from './NetworkCard.vue'
import WifiUpdater from './WifiUpdater.vue'

const wifi_store: WifiStore = getModule(WifiStore)

export default Vue.extend({
  name: 'WifiManager',
  components: {
    NetworkCard,
    SpinningLogo,
    ConnectionDialog,
    DisconnectionDialog,
    WifiUpdater,
  },
  data() {
    return {
      selected_network: null as Network | null,
      show_connection_dialog: false,
      show_disconnection_dialog: false,
    }
  },
  computed: {
    wifi_status(): WifiStatus | null {
      return wifi_store.network_status
    },
    current_network(): Network | null {
      return wifi_store.current_network
    },
    connectable_networks(): Network[] {
      let showable_networks = wifi_store.available_networks
      const { current_network } = wifi_store
      if (current_network) {
        showable_networks = showable_networks.filter((network: Network) => network.ssid !== current_network.ssid)
      }
      return showable_networks.sort((a: Network, b: Network) => b.signal - a.signal)
    },
    are_connectable_networks_available(): boolean {
      return this.connectable_networks.length !== 0
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
  },
})
</script>

<style>
  .connected-network {
      background-color: #2799D2
  }

  .connected-network:hover {
      cursor: pointer;
  }

  .available-network {
      background-color: #f8f8f8;
  }

  .available-network:hover {
      cursor: pointer;
      background-color: #c5c5c5;
  }
</style>
