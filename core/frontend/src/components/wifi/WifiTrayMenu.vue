<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="500"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        id="wifi-tray-menu-button"
        class="px-1"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon color="white">
          {{ wifi_icon }}
        </v-icon>
      </v-card>
    </template>
    <wifi-manager />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import wifi from '@/store/wifi'
import { wifi_strenght_icon } from '@/utils/wifi'

import WifiManager from './WifiManager.vue'

export default Vue.extend({
  name: 'WifiTrayMenu',
  components: {
    WifiManager,
  },
  computed: {
    wifi_icon(): string {
      if (wifi.connectable_networks === null) {
        return 'mdi-wifi-sync'
      }
      if (wifi.current_network === null) {
        return 'mdi-wifi-off'
      }
      return wifi_strenght_icon(wifi.current_network.signal)
    },
  },
})
</script>

<style>
</style>
