<template>
  <v-card
    v-tooltip="'Battery'"
    class="d-flex align-center justify-center battery-card"
    height="40"
  >
    <div class="battery-info-container">
      <div class="battery-info-row">
        <v-icon small class="battery-icon">
          mdi-car-battery
        </v-icon>
        <div class="battery-value">
          {{ battery_voltage }}
        </div>
      </div>
      <div class="battery-info-row">
        <v-icon small class="battery-icon">
          mdi-current-dc
        </v-icon>
        <div class="battery-value">
          {{ battery_current }}
        </div>
      </div>
    </div>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink from '@/store/mavlink'
import mavlink_store_get from '@/utils/mavlink'

export default Vue.extend({
  name: 'BatteryWidget',
  computed: {
    battery_voltage(): string {
      const voltage_millivolts = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.voltage_battery') as number
      if (voltage_millivolts === undefined || voltage_millivolts === 65535) {
        return 'Loading..'
      }
      return `${(voltage_millivolts / 1000).toFixed(2)} V`
    },
    battery_current(): string {
      const current_centiampere = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.current_battery') as number
      if (current_centiampere === undefined || current_centiampere === -1) {
        return 'Loading..'
      }
      return `${(current_centiampere / 100).toFixed(2)} A`
    },
  },
})
</script>

<style scoped>
.battery-card {
  border-radius: 4px;
  padding-left: 8px;
  padding-right: 8px;
}

.battery-info-container {
  display: flex;
  flex-direction: column;
  font-size: 0.8rem;
  line-height: 1.1;
  min-width: 70px;
}

.battery-icon {
  margin-right: 2px;
  font-size: 0.9rem !important;
}

.battery-info-row {
  display: flex;
  align-items: center;
}

.battery-value {
  flex: 1;
  text-align: right;
}
</style>
