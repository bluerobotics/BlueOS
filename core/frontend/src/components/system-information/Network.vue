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
import system_information, { FetchType } from '@/store/system-information'
import { Network } from '@/types/system-information/system'

const FETCH_TYPES = [FetchType.SystemNetworkType]

export default Vue.extend({
  name: 'Network',
  components: {
    NetworkCard,
  },
  computed: {
    networks(): Network[] {
      // Copy before sort — do not mutate the Vuex network array in place.
      const networks = system_information.system?.network ?? []
      return [...networks].sort((first, second) => first.name.localeCompare(second.name))
    },
  },
  mounted() {
    system_information.subscribeSystemInformation(FETCH_TYPES)
  },
  beforeDestroy() {
    system_information.unsubscribeSystemInformation(FETCH_TYPES)
  },
})
</script>
