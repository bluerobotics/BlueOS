<template>
  <v-card class="d-flex align-center justify-center" height="40">
    <v-card-title>
      Disk: {{ disk_usage }}%
    </v-card-title>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import system_information, { FetchType } from '@/store/system-information'
import { Disk } from '@/types/system-information/system'

export default Vue.extend({
  name: 'DiskWidget',
  data() {
    return {
      timer: 0,
    }
  },
  computed: {
    main_disk(): undefined | Disk {
      const disks = system_information.system?.disk
      return disks?.find((sensor) => sensor.mount_point === '/')
    },
    disk_usage(): string {
      return (this.main_disk ? 100 - this.main_disk.available_space_B / this.main_disk.total_space_B / 0.01 : undefined)
        ?.toFixed() || '-'
    },
  },
  mounted() {
    this.timer = setInterval(() => system_information.fetchSystemInformation(FetchType.SystemDiskType), 30000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
})
</script>
