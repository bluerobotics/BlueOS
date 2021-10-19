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
import { wifi_strenght_icon } from '@/utils/wifi'

import WifiManager from './WifiManager.vue'

const wifi_store: WifiStore = getModule(WifiStore)

export default Vue.extend({
  name: 'WifiTrayMenu',
  components: {
    WifiManager,
  },
  computed: {
    wifi_icon(): string {
      if (wifi_store.connectable_networks === null) {
        return 'mdi-wifi-sync'
      }
      if (wifi_store.current_network === null) {
        return 'mdi-wifi-off'
      }
      return wifi_strenght_icon(wifi_store.current_network.signal)
    },
  },
})
</script>

<style>
</style>
