<template>
  <v-card class="d-flex flex-column" height="100%">
    <v-card-text class="d-flex flex-row justify-space-around align-center flex-grow-1">
      <div class="d-flex flex-column align-center">
        <div class="text-caption mb-2">
          CPU Usage
        </div>
        <v-progress-circular
          :value="cpuUsage"
          :color="getColor(cpuUsage)"
          :size="circleSize"
          :width="circleWidth"
        >
          {{ cpuUsage }}%
        </v-progress-circular>
      </div>
      <div class="d-flex flex-column align-center">
        <div class="text-caption mb-2">
          Memory Usage
        </div>
        <v-progress-circular
          :value="memoryUsage"
          :color="getColor(memoryUsage)"
          :size="circleSize"
          :width="circleWidth"
        >
          {{ memoryUsage }}%
        </v-progress-circular>
      </div>
      <div class="d-flex flex-column align-center">
        <div class="text-caption mb-2">
          Disk Usage
        </div>
        <v-progress-circular
          :value="diskUsage"
          :color="getColor(diskUsage)"
          :size="circleSize"
          :width="circleWidth"
        >
          {{ diskUsage }}%
        </v-progress-circular>
      </div>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import { OneMoreTime } from '@/one-more-time'
import system_information, { FetchType } from '@/store/system-information'

export default Vue.extend({
  name: 'CpuPie',
  data() {
    return {
      timer: new OneMoreTime({ delay: 2000, disposeWith: this }),
      containerWidth: 0,
    }
  },
  computed: {
    cpuUsage(): number {
      const cpus = system_information.system?.cpu
      if (!cpus || cpus.length === 0) return 0
      return Math.round(cpus.map((cpu) => cpu.usage).reduce((a, b) => a + b) / cpus.length)
    },
    memoryUsage(): number {
      const memory = system_information.system?.memory
      if (!memory || memory.ram.total_kB === 0) return 0
      return Math.round(memory.ram.used_kB / memory.ram.total_kB * 100)
    },
    diskUsage(): number {
      const mainDisk = system_information.system?.disk?.find((disk) => disk.mount_point === '/')
      if (!mainDisk || mainDisk.total_space_B === 0) return 0
      return Math.round(100 - mainDisk.available_space_B / mainDisk.total_space_B * 100)
    },
    circleSize(): number {
      // Calculate size based on container width
      // Each circle should be about 1/4 of the container width, but not larger than 80px or smaller than 40px
      const size = Math.min(80, Math.floor(this.containerWidth / 4) - 16) // 16px for margins
      return Math.max(40, size)
    },
    circleWidth(): number {
      return Math.max(4, Math.floor(this.circleSize / 10))
    },
  },
  mounted() {
    this.timer.setAction(() => {
      system_information.fetchSystemInformation(FetchType.SystemCpuType)
      system_information.fetchSystemInformation(FetchType.SystemMemoryType)
      system_information.fetchSystemInformation(FetchType.SystemDiskType)
    })

    this.updateContainerWidth()
    window.addEventListener('resize', this.updateContainerWidth)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.updateContainerWidth)
  },
  methods: {
    getColor(value: number): string {
      if (value >= 90) return 'error'
      if (value >= 70) return 'warning'
      return 'success'
    },
    updateContainerWidth() {
      if (!this.$el || !(this.$el instanceof HTMLElement)) return
      this.containerWidth = this.$el.clientWidth
    },
  },
})
</script>

<style scoped>
.v-progress-circular {
  margin: 0 8px;
}
</style>
