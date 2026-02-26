<template>
  <v-sheet
    class="network-card"
    :color="connected ? 'primary' : ''"
  >
    <v-row
      flat
      class="d-flex align-center pa-0 ma-0"
      @click="emitClick"
    >
      <v-col :cols="1" />

      <v-col
        :cols="6"
        class="d-flex flex-column justify-center"
      >
        <span>{{ network_name }}</span>
        <span
          v-if="ipAddress !== ''"
          class="text-subtitle-2"
        >
          {{ ipAddress }}
        </span>
      </v-col>

      <v-col
        :cols="1"
        class="d-flex justify-center"
      >
        <v-chip
          small
          :color="frequency_band_color"
          class="frequency-chip"
          label
        >
          {{ frequency_band }}
        </v-chip>
      </v-col>

      <v-col :cols="1">
        <v-icon class="d-flex flex-justify-center">
          {{ network_saved_icon }}
        </v-icon>
      </v-col>

      <v-col :cols="1">
        <v-icon class="d-flex flex-justify-center">
          {{ network_protection_icon }}
        </v-icon>
      </v-col>

      <v-col :cols="1">
        <v-icon class="d-flex flex-justify-center">
          {{ signal_strength_icon }}
        </v-icon>
      </v-col>

      <v-col :cols="1" />
    </v-row>
  </v-sheet>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { Network } from '@/types/wifi'
import { wifi_strenght_icon } from '@/utils/wifi'

export default Vue.extend({
  name: 'WifiNetworkCard',
  props: {
    connected: {
      type: Boolean,
      default: false,
      required: false,
    },
    network: {
      type: Object as PropType<Network>,
      required: true,
    },
    ipAddress: {
      type: String,
      default: '',
      required: false,
    },
  },
  computed: {
    network_saved_icon(): string {
      return this.network.saved ? 'mdi-content-save' : ''
    },
    network_name(): string {
      if (this.network.ssid === null || this.network.ssid === '') {
        return '[HIDDEN SSID]'
      }
      return this.network.ssid
    },
    network_protection_icon(): string {
      return this.network.locked ? 'mdi-lock' : 'mdi-lock-open-outline'
    },
    signal_strength_icon(): string {
      return wifi_strenght_icon(this.network.signal)
    },
    frequency_band(): string {
      const freq = this.network.frequency
      if (freq >= 5925) return '6G'
      if (freq >= 5000) return '5G'
      return '2.4G'
    },
    frequency_band_color(): string {
      const freq = this.network.frequency
      if (freq >= 5925) return 'purple'
      if (freq >= 5000) return 'green'
      return 'orange'
    },
  },
  methods: {
    emitClick(): void {
      this.$emit('click', this.network)
    },
  },
})
</script>

<style>
  .network-card:hover {
    cursor: pointer;
    background-color: #2174aa;
  }
  .frequency-chip {
    font-size: 11px !important;
    height: 20px !important;
    min-width: 32px !important;
    padding: 0 4px !important;
    font-weight: 600;
    justify-content: center;
  }
</style>
