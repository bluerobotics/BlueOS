<template>
  <v-card
    flat
    class="ma-3 d-flex flex-wrap justify-center"
  >
    <network-card
      v-for="(network, i) in networks"
      :key="i"
      :network="network"
    />
    <v-card>
      <v-skeleton-loader
        v-if="networks.isEmpty()"
        v-bind="attrs"
        class="mx-auto"
        min-width="400"
        type="article, list-item@5"
      />
    </v-card>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import NetworkCard from '@/components/system-information/NetworkCard.vue'
import system_information from '@/store/system-information'
import { Network } from '@/types/system-information/system'

export default Vue.extend({
  name: 'Network',
  components: {
    NetworkCard,
  },
  data() {
    return {
      timer: 0,
    }
  },
  computed: {
    networks(): Network[] {
      return system_information.system?.network.sort((first, second) => first.name.localeCompare(second.name)) ?? []
    },
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
})
</script>
