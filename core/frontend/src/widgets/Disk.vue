<template>
  <v-card class="d-flex align-center justify-center disk-card" height="40">
    <div class="disk-widget-content">
      <v-icon small class="disk-icon-main">
        mdi-harddisk
      </v-icon>

      <div class="disk-info-container">
        <div class="disk-info-row">
          <div>{{ disk_space_with_percentage }}</div>
        </div>

        <div class="disk-info-row">
          <div>W: {{ disk_write_rate }}</div>
        </div>
      </div>
    </div>
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
    disk_space_with_percentage(): string {
      if (!this.main_disk) {
        return 'Loading..'
      }

      const usedBytes = this.main_disk.total_space_B - this.main_disk.available_space_B
      const totalBytes = this.main_disk.total_space_B
      const usagePercentage = this.disk_usage

      return `${this.formatBytesCompact(usedBytes)}/${this.formatBytesCompact(totalBytes)}GB (${usagePercentage}%)`
    },
    disk_write_rate(): string {
      if (!this.main_disk || this.main_disk.write_rate_Bps === undefined) {
        return 'Loading..'
      }

      const rateBytesPerSecond = this.main_disk.write_rate_Bps
      return this.formatBytesPerSecond(rateBytesPerSecond)
    },
  },
  mounted() {
    this.timer = setInterval(() => system_information.fetchSystemInformation(FetchType.SystemDiskType), 5000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    formatBytesCompact(bytes: number): string {
      return `${(bytes / (1024 * 1024 * 1024)).toFixed(0)}`
    },
    formatBytesPerSecond(bytesPerSecond: number): string {
      const absBytes = Math.abs(bytesPerSecond)

      if (absBytes < 1024) {
        return `${absBytes.toFixed(0)} B/s`
      } if (absBytes < 1024 * 1024) {
        return `${(absBytes / 1024).toFixed(1)} KB/s`
      } if (absBytes < 1024 * 1024 * 1024) {
        return `${(absBytes / (1024 * 1024)).toFixed(1)} MB/s`
      }
      return `${(absBytes / (1024 * 1024 * 1024)).toFixed(1)} GB/s`
    },
  },
})
</script>

<style scoped>
.disk-card {
  border-radius: 4px;
  padding-left: 8px;
  padding-right: 8px;
}

.disk-widget-content {
  display: flex;
  align-items: center;
  min-width: 120px;
  gap: 8px;
}

.disk-icon-main {
  font-size: 1.7rem !important;
  color: rgba(var(--v-theme-on-surface), 0.8);
}

.disk-info-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  font-size: 0.7rem;
  line-height: 1.1;
}

.disk-info-row {
  display: flex;
  align-items: center;
  margin-bottom: 1px;
}

.disk-info-row:last-child {
  margin-bottom: 0;
}
</style>
