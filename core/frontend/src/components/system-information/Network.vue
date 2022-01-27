<template>
  <v-row

    class="ma-5"
  >
    <network-card
      v-for="(network, i) in networks"
      :key="i"
      :network="network"
      class="ma-5"
    />
    <v-card>
      <v-skeleton-loader
        v-if="networks.length === 0"
        v-bind="attrs"
        class="mx-auto"
        min-width="400"
        type="article, list-item@5"
      />
    </v-card>
  </v-row>
</template>

<script lang="ts">
import NetworkCard from '@/components/system-information/NetworkCard.vue'
import system_information from '@/store/system-information'
import { Network } from '@/types/system-information/system'

export default {
  name: 'Network',
  components: {
    NetworkCard,
  },
  computed: {
    networks(): Network[] {
      return system_information.system?.network ?? []
    },
  },
}
</script>
