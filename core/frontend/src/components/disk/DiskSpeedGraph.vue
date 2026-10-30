<template>
  <apexchart
    :key="chartKey"
    type="line"
    :options="chartOptions"
    :series="chartSeries"
  />
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import settingsStore from '@/store/settings'
import { DiskSpeedTestPoint } from '@/types/disk'

export default Vue.extend({
  name: 'DiskSpeedGraph',
  props: {
    data: {
      type: Array as PropType<DiskSpeedTestPoint[]>,
      required: true,
    },
  },
  computed: {
    chartKey(): string {
      return `chart-${this.data.length}`
    },
    chartOptions(): Record<string, unknown> {
      return {
        chart: {
          animations: {
            enabled: true,
          },
          toolbar: {
            show: false,
          },
        },
        theme: {
          mode: settingsStore.is_dark_theme ? 'dark' : 'light',
        },
        stroke: {
          curve: 'smooth',
          width: 3,
        },
        markers: {
          size: [8, 8],
          strokeWidth: 2,
          strokeColors: ['#4CAF50', '#2196F3'],
          hover: {
            size: 10,
          },
          showNullDataPoints: false,
        },
        dataLabels: {
          enabled: true,
          formatter(val: number) {
            return val ? `${val.toFixed(1)}` : ''
          },
          offsetY: -10,
        },
        xaxis: {
          categories: this.data.map((p) => `${p.size_mb} MB`),
          title: {
            text: 'Test Size',
          },
        },
        yaxis: {
          title: {
            text: 'Speed (MiB/s)',
          },
          decimalsInFloat: 1,
          min: 0,
        },
        legend: {
          position: 'top',
        },
        colors: ['#4CAF50', '#2196F3'],
      }
    },
    chartSeries(): { name: string; data: (number | null)[] }[] {
      return [
        {
          name: 'Write',
          data: this.data.map((p) => p.write_speed ?? null),
        },
        {
          name: 'Read',
          data: this.data.map((p) => p.read_speed ?? null),
        },
      ]
    },
  },
})
</script>
