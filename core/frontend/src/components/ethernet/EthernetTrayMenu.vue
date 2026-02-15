<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="400"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        id="ethernet-tray-menu-button"
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          v-tooltip="interface_connected_tooltip"
          class="px-1"
          color="white"
        >
          {{ interface_connected_icon }}
        </v-icon>
      </v-card>
    </template>
    <ethernet-manager />
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import ethernet from '@/store/ethernet'

import EthernetManager from './EthernetManager.vue'

export default Vue.extend({
  name: 'EthernetTrayMenu',
  components: {
    EthernetManager,
  },
  computed: {
    interface_connected_icon(): string {
      const connected_interfaces = ethernet.available_interfaces
        .filter((ethernet_interface) => ethernet_interface.info && ethernet_interface.info.connected)
      return connected_interfaces.isEmpty() ? 'mdi-lan-disconnect' : 'mdi-lan-connect'
    },
    interface_connected_tooltip(): string {
      const connected_interfaces = ethernet.available_interfaces
        .filter((ethernet_interface) => ethernet_interface.info?.connected)
      return connected_interfaces.isEmpty() ? 'Ethernet disconnected' : 'Ethernet connected'
    },
  },
})
</script>
