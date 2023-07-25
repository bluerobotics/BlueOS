<template>
  <v-card
    class="ma-3"
    min-width="340"
  >
    <v-list-item two-line>
      <v-list-item-content>
        <v-list-item-title class="text-h6">
          {{ network.name }} {{ network.is_loopback ? '(loopback)' : '' }}
        </v-list-item-title>
        <v-list-item-subtitle v-if="network.description">
          Description: {{ network.description }}
        </v-list-item-subtitle>
      </v-list-item-content>
    </v-list-item>

    <v-card-text class="pa-0">
      <v-col
        align="h-center"
        class="pa-0"
      >
        <v-col
          v-for="(ip, i) in network.ips"
          :key="i"
          class="pa-0 text-h6 text-center"
          :style="ip.includes(':') && !show_ipv6 ? 'cursor: pointer; filter:blur(0.5em)' : ''"
          @click="show_ipv6 = true"
        >
          {{ ip }}
        </v-col>
      </v-col>
    </v-card-text>

    <v-list-item>
      <v-list-item-icon>
        <v-icon>
          mdi-network
        </v-icon>
      </v-list-item-icon>
      <v-list-item-subtitle>{{ network.is_up ? 'Enabled' : 'Disabled' }}</v-list-item-subtitle>
    </v-list-item>

    <v-list-item>
      <v-list-item-icon>
        <v-icon>
          mdi-badge-account-horizontal
        </v-icon>
      </v-list-item-icon>
      <v-list-item-subtitle>MAC:</v-list-item-subtitle>
      <v-list-item-subtitle
        class="text-right"
        :style="show_mac ? '' : 'cursor: pointer; filter:blur(0.5em)'"
        @click="show_mac = true"
      >
        {{ network.mac }}
      </v-list-item-subtitle>
    </v-list-item>

    <v-list-item>
      <v-list-item-icon>
        <v-icon>
          mdi-package-down
        </v-icon>
      </v-list-item-icon>
      <v-list-item-subtitle>Received package:</v-list-item-subtitle>
      <v-list-item-subtitle class="text-right">
        {{ network.total_packets_received }}
      </v-list-item-subtitle>
    </v-list-item>

    <v-list-item>
      <v-list-item-icon>
        <v-icon>
          mdi-package-up
        </v-icon>
      </v-list-item-icon>
      <v-list-item-subtitle>Transmitted package:</v-list-item-subtitle>
      <v-list-item-subtitle class="text-right">
        {{ network.total_packets_transmitted }}
      </v-list-item-subtitle>
    </v-list-item>

    <v-list-item>
      <v-list-item-icon>
        <v-icon>
          mdi-cloud-upload
        </v-icon>
      </v-list-item-icon>
      <v-list-item-subtitle>Bytes received:</v-list-item-subtitle>
      <v-list-item-subtitle class="text-right">
        {{ network.total_received_B }}
      </v-list-item-subtitle>
    </v-list-item>

    <v-list-item>
      <v-list-item-icon>
        <v-icon>
          mdi-cloud-download
        </v-icon>
      </v-list-item-icon>
      <v-list-item-subtitle>Bytes transmitted:</v-list-item-subtitle>
      <v-list-item-subtitle class="text-right">
        {{ network.total_transmitted_B }}
      </v-list-item-subtitle>
    </v-list-item>
  </v-card>
</template>

<script lang="ts">
import { PropType } from 'vue'

import { Network } from '@/types/system-information/system'

export default {
  name: 'NetworkCard',
  props: {
    network: {
      type: Object as PropType<Network>,
      required: true,
    },
  },
  data() {
    return {
      show_mac: false,
      show_ipv6: false,
    }
  },
}
</script>
