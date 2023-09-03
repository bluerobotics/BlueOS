<template>
  <v-card class="d-flex align-center justify-center" height="40">
    <v-card-title>
      CPU: {{ cpu_usage }} %
    </v-card-title>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information, { FetchType } from '@/store/system-information'

export default Vue.extend({
  name: 'CpuWidget',
  data() {
    return {
      timer: 0,
    }
  },
  computed: {
    cpu_usage(): string {
      const cpus = system_information.system?.cpu
      if (!cpus) {
        return '-'
      }
      return (cpus.map((cpu) => cpu.usage).reduce((a, b) => a + b) / cpus.length).toFixed()
    },
  },
  mounted() {
    this.timer = setInterval(() => system_information.fetchSystemInformation(FetchType.SystemCpuType), 5000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
})
</script>
