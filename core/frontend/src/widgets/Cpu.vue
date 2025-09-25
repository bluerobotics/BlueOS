<template>
  <v-card class="d-flex align-center justify-center cpu-card" height="40">
    <div class="cpu-bars-container">
      <div
        v-for="(usage, index) in cpus_usage"
        :key="`cpu-${index}`"
        class="cpu-bar-container"
        :title="`CPU ${index}: ${usage.toFixed(1)}%`"
      >
        <div
          class="cpu-bar"
          :style="{
            height: `${Math.max(usage * 0.32, 1)}px`,
            backgroundColor: getBarColor(usage),
          }"
        />
      </div>
    </div>

    <div class="cpu-info-container">
      <div class="cpu-info-row clock-row">
        <v-icon small class="cpu-icon">
          mdi-speedometer
        </v-icon>
        <div v-if="clockDisplay.single">
          {{ clockDisplay.single }}GHz
        </div>
        <div v-else>
          {{ clockDisplay.max }}-{{ clockDisplay.min }}GHz
        </div>
      </div>

      <div class="cpu-info-row temp-row">
        <v-icon small class="cpu-icon">
          mdi-thermometer
        </v-icon>
        <div>{{ cpu_temperature }}°C</div>
      </div>
    </div>
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
    cpus_usage(): number[] {
      const cpus = system_information.system?.cpu
      if (!cpus) {
        return []
      }
      return cpus.map((cpu) => cpu.usage)
    },
    cpu_clock(): number[] {
      const cpus = system_information.system?.cpu
      if (!cpus) {
        return []
      }
      return cpus.map((cpu) => cpu.frequency)
    },
    cpu_temperature(): string {
      const temperature_sensors = system_information.system?.temperature
      const main_sensor = temperature_sensors?.find(
        (sensor) => sensor.name.toLowerCase().includes('cpu')
          || sensor.name.toLowerCase().includes('soc')
          || sensor.name.toLowerCase().includes('ccd'),
      )
      return main_sensor ? main_sensor.temperature.toFixed(1) : 'Loading..'
    },
    clockDisplay(): { single: string | null; max?: string | null; min?: string | null } {
      if (this.cpu_clock.length === 0) {
        return { single: null, max: null, min: null }
      }

      const clocksInGhz = this.cpu_clock.map((clock: number) => clock / 1000)
      const allEqual = clocksInGhz.every((clock: number) => clock === clocksInGhz[0])

      if (allEqual) {
        return { single: clocksInGhz[0].toFixed(1) }
      }
      const max = Math.max(...clocksInGhz)
      const min = Math.min(...clocksInGhz)
      return {
        max: max.toFixed(1),
        min: min.toFixed(1),
        single: null,
      }
    },
  },
  mounted() {
    this.timer = setInterval(() => system_information.fetchSystemInformation(FetchType.SystemCpuType), 5000)
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    getBarColor(usage: number): string {
      if (usage < 40) return '#4caf50' // Green
      if (usage < 75) return '#ff9800' // Orange
      return '#f44336' // Red
    },
  },
})
</script>

<style scoped>
.cpu-card {
  border-radius: 4px;
  padding-left: 4px;
  padding-right: 4px;
}

.cpu-bars-container {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  margin-right: 12px;
}

.cpu-bar-container {
  width: 8px;
  height: 32px;
  border: 1px solid var(--v-outline-darken3);
  border-radius: 3px;
  display: flex;
  align-items: flex-end;
  background-color: var(--v-sheet_bg-darken1);
}

.cpu-bar {
  width: 100%;
  border-radius: 1px;
  transition: height 0.3s ease, background-color 0.3s ease;
}

.cpu-info-container {
  display: flex;
  flex-direction: column;
  font-size: 0.8rem;
  line-height: 1.1;
  min-width: 70px;
}

.cpu-icon {
  margin-right: 2px;
  font-size: 0.9rem !important;
}

.cpu-info-row {
  display: flex;
  align-items: center;
}

.clock-row .cpu-icon {
  margin-bottom: 2px;
}
</style>
