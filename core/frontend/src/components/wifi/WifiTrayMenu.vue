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
import { getModule } from 'vuex-module-decorators'

import WifiStore from '@/store/wifi'
import wifi_status_icon from '@/utils/wifi'

import WifiManager from './WifiManager.vue'

const wifi_store: WifiStore = getModule(WifiStore)

export default Vue.extend({
  name: 'WifiTrayMenu',
  components: {
    WifiManager,
  },
  computed: {
    wifi_icon(): string {
      const signal = wifi_store.current_network ? wifi_store.current_network.signal : -1000
      return wifi_status_icon(signal)
    },
  },
})
</script>

<style>
</style>
