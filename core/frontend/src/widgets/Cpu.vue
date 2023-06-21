<template>
  <v-card class="d-flex align-center justify-center" height="40">
    <v-card-title>
      CPU: {{ cpu_usage }} %
    </v-card-title>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information from '@/store/system-information'

export default Vue.extend({
  name: 'CpuWidget',
  computed: {
    cpu_usage(): string {
      const cpus = system_information.system?.cpu
      if (!cpus) {
        return '-'
      }
      return (cpus.map((cpu) => cpu.usage).reduce((a, b) => a + b) / cpus.length).toFixed()
    },
  },
})
</script>
