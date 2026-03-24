<template>
  <div v-if="params_finished_loaded" class="power-container pa-4">
    <battery-card
      title="Battery 1"
      :monitor-param="parameter('BATT_MONITOR')"
      :capacity-param="parameter('BATT_CAPACITY')"
      :arm-volt-param="parameter('BATT_ARM_VOLT')"
      :volt-pin-param="parameter('BATT_VOLT_PIN')"
      :curr-pin-param="parameter('BATT_CURR_PIN')"
      :volt-mult-param="parameter('BATT_VOLT_MULT')"
      :amp-per-volt-param="parameter('BATT_AMP_PERVLT')"
      :amp-offset-param="parameter('BATT_AMP_OFFSET')"
      :voltage="battery_voltage"
      :current="battery_current"
    />
    <battery-card
      v-if="parameter('BATT2_MONITOR')"
      title="Battery 2"
      :monitor-param="parameter('BATT2_MONITOR')"
      :capacity-param="parameter('BATT2_CAPACITY')"
      :arm-volt-param="parameter('BATT2_ARM_VOLT')"
      :volt-pin-param="parameter('BATT2_VOLT_PIN')"
      :curr-pin-param="parameter('BATT2_CURR_PIN')"
      :volt-mult-param="parameter('BATT2_VOLT_MULT')"
      :amp-per-volt-param="parameter('BATT2_AMP_PERVLT')"
      :amp-offset-param="parameter('BATT2_AMP_OFFSET')"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import Parameter from '@/types/autopilot/parameter'
import mavlink_store_get from '@/utils/mavlink'

import BatteryCard from './BatteryCard.vue'

export default Vue.extend({
  name: 'PowerConfiguration',
  components: {
    BatteryCard,
  },
  computed: {
    params_finished_loaded(): boolean {
      return autopilot_data.finished_loading
    },
    battery_voltage(): number {
      const voltage_microvolts = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.voltage_battery') as number
      return voltage_microvolts / 1000
    },
    battery_current(): number {
      const current_centiampere = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.current_battery') as number
      return current_centiampere / 100
    },
  },
  methods: {
    parameter(name: string): Parameter | undefined {
      return autopilot_data.parameter(name)
    },
  },
})
</script>

<style scoped>
.power-container {
  max-width: 700px;
  margin: 0 auto;
}
</style>
