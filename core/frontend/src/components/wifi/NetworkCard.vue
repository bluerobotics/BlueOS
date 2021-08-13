<template>
  <v-row
    flat
    @click="emitClick"
  >
    <v-col :cols="1" />

    <v-col :cols="7">
      {{ network_name }}
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
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { Network } from '@/types/wifi.d'

export default Vue.extend({
  name: 'NetworkCard',
  props: {
    network: {
      type: Object as PropType<Network>,
      required: true,
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
      /*eslint-disable */
      // | Signal Strength | TL;DR     |  Description                                                                                                                               |
      // |-----------------|-----------|--------------------------------------------------------------------------------------------------------------------------------------------|
      // | -30 dBm         | Amazing   | Max achievable signal strength. The client can only be a few feet from the AP to achieve this. Not typical or desirable in the real world. |
      // | -67 dBm         | Very Good | Minimum signal strength for applications that require very reliable, timely delivery of data packets.                                      |
      // | -70 dBm         | Okay      | Minimum signal strength for reliable packet delivery.                                                                                      |
      // | -80 dBm         | Not Good  | Minimum signal strength for basic connectivity. Packet delivery may be unreliable.                                                         |
      // | -90 dBm         | Unusable  | Approaching or drowning in the noise floor. Any functionality is highly unlikely.                                                           |
      // Reference: metageek.com/training/resources/wifi-signal-strength-basics.html
      /* eslint-enable */

      if (this.network.signal >= -30) return 'mdi-wifi-strength-4'
      if (this.network.signal >= -67) return 'mdi-wifi-strength-3'
      if (this.network.signal >= -70) return 'mdi-wifi-strength-2'
      if (this.network.signal >= -80) return 'mdi-wifi-strength-1'
      return 'mdi-wifi-strength-outline'
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
</style>
