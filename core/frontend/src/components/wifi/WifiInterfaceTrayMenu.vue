<template>
  <div>
    <v-menu
      :close-on-content-click="false"
      nudge-left="500"
      nudge-bottom="25"
    >
      <template
        #activator="{ on, attrs }"
      >
        <v-card
          class="px-1 d-flex align-center"
          elevation="0"
          color="transparent"
          v-bind="attrs"
          v-on="on"
        >
          <v-icon
            v-tooltip="{
              content: tooltipContent,
              bottom: true,
              offset: 5,
            }"
            color="white"
          >
            {{ wifi_icon }}
          </v-icon>
        </v-card>
      </template>
      <wifi-interface-manager
        :interface-name="interfaceName"
      />
    </v-menu>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import wifi from '@/store/wifi'
import { WifiInterface } from '@/types/wifi'
import { wifi_strenght_icon } from '@/utils/wifi'

import WifiInterfaceManager from './WifiInterfaceManager.vue'

export default Vue.extend({
  name: 'WifiInterfaceTrayMenu',
  components: {
    WifiInterfaceManager,
  },
  props: {
    interfaceName: {
      type: String,
      required: true,
    },
  },
  computed: {
    interface_data(): WifiInterface | undefined {
      return wifi.wifi_interfaces.find((iface) => iface.name === this.interfaceName)
    },
    wifi_icon(): string {
      if (!this.interface_data) {
        return 'mdi-wifi-sync'
      }
      if (!this.interface_data.connected) {
        return 'mdi-wifi-off'
      }
      if (this.interface_data.signal_strength !== null) {
        return wifi_strenght_icon(this.interface_data.signal_strength)
      }
      return 'mdi-wifi'
    },
    tooltipContent(): string {
      if (!this.interface_data) {
        return `${this.interfaceName}: Loading...`
      }
      if (!this.interface_data.connected) {
        return `${this.interfaceName}: Disconnected`
      }
      let content = `${this.interfaceName}: ${this.interface_data.ssid || 'Connected'}`
      if (this.interface_data.ip_address) {
        content += ` (${this.interface_data.ip_address})`
      }
      return content
    },
  },
})
</script>

<style scoped>
</style>
