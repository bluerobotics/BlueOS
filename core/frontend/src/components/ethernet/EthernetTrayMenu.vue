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
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
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
import { getModule } from 'vuex-module-decorators'

import EthernetStore from '@/store/ethernet'

import EthernetManager from './EthernetManager.vue'

const ethernet_store: EthernetStore = getModule(EthernetStore)

export default Vue.extend({
  name: 'EthernetTrayMenu',
  components: {
    EthernetManager,
  },
  computed: {
    interface_connected_icon(): string {
      const connected_interfaces = ethernet_store.available_interfaces
        .filter((ethernet_interface) => ethernet_interface.info && ethernet_interface.info.connected)
      return connected_interfaces.length !== 0 ? 'mdi-lan-connect' : 'mdi-lan-disconnect'
    },
  },
})
</script>

<style>
</style>
