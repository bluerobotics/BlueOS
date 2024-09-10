<template>
  <v-card class="d-flex align-center justify-center" height="40">
    <v-card-title>
      <v-icon>mdi-arrow-up</v-icon>
      {{ formatBandwidth(upload) }}
      <v-icon>mdi-arrow-down</v-icon>
      {{ formatBandwidth(download) }}
    </v-card-title>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import { OneMoreTime } from '@/one-more-time'
import system_information, { FetchType } from '@/store/system-information'

export default Vue.extend({
  name: 'CpuWidget',
  data() {
    return {
      timer: 0,
      check_backend_status_task: new OneMoreTime({ delay: 2000, disposeWith: this }),
    }
  },
  computed: {
    upload(): number {
      const eth0 = system_information.system?.network?.find((iface) => iface.name === 'eth0')
      return eth0?.upload_speed ?? 0
    },
    download(): number {
      const eth0 = system_information.system?.network?.find((iface) => iface.name === 'eth0')
      return eth0?.download_speed ?? 0
    },
  },
  mounted() {
    this.check_backend_status_task.setAction(() => {
      system_information.fetchSystemInformation(FetchType.SystemNetworkType)
    })
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    formatBandwidth(bytesPerSecond: number): string {
      const units = ['bps', 'kbps', 'Mbps', 'Gbps']
      const base = 1000

      if (bytesPerSecond <= 0) return '0 bps'

      const bitsPerSecond = bytesPerSecond * 8

      const unitIndex = Math.max(0, Math.min(
        Math.floor(Math.log(bitsPerSecond) / Math.log(base)),
        units.length - 1,
      ))

      const exp = Math.min(Math.floor(Math.log(bytesPerSecond * 8) / Math.log(base)), units.length - 1)
      const value = bytesPerSecond * 8 / base ** exp

      return `${value.toFixed(2)} ${units[unitIndex]}`
    },
  },
})
</script>
