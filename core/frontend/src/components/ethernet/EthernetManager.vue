<template>
  <v-card
    elevation="1"
    width="400"
  >
    <v-expansion-panels v-if="are_interfaces_available && !updating_interfaces">
      <interface-card
        v-for="(ethernet_interface, key) in available_interfaces"
        :key="key"
        :adapter="ethernet_interface"
      />
    </v-expansion-panels>
    <v-container v-else-if="updating_interfaces">
      <spinning-logo
        size="30%"
        subtitle="Fetching available ethernet interfaces..."
      />
    </v-container>
    <v-container v-else>
      <div>
        No ethernet interfaces available
      </div>
    </v-container>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import ethernet from '@/store/ethernet'
import { EthernetInterface } from '@/types/ethernet'

import InterfaceCard from './InterfaceCard.vue'

export default Vue.extend({
  name: 'EthernetManager',
  components: {
    InterfaceCard,
    SpinningLogo,
  },
  computed: {
    are_interfaces_available(): boolean {
      return ethernet.available_interfaces.length > 0
    },
    available_interfaces(): EthernetInterface[] {
      return ethernet.available_interfaces
    },
    updating_interfaces(): boolean {
      return ethernet.updating_interfaces
    },
  },
})
</script>
