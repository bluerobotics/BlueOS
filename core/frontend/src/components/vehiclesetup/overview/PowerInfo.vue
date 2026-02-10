<template>
  <v-card class="pa-2">
    <v-card-title class="align-center">
      Battery Monitor
    </v-card-title>
    <v-card-text>
      <div class="d-flex justify-space-between mb-3">
        <span><b>Voltage:</b> {{ battery_voltage }} V</span>
        <span><b>Current:</b> {{ battery_current }} A</span>
      </div>

      <div v-if="is_known_power_meter">
        <b>{{ is_known_power_meter }}</b>
      </div>
      <div
        v-else
      >
        <span class="d-block"><b>Voltage Pin:</b> {{ printParam(batt_monitor.vPin) }}</span>
        <span class="d-block"><b>Voltage Multiplier:</b> {{ printParam(batt_monitor.vMulti) }}</span>
        <span class="d-block"><b>Current Pin:</b> {{ printParam(batt_monitor.aPin) }}</span>
        <span class="d-block"><b>Current per Volt:</b> {{ printParam(batt_monitor.aPv) }}</span>
        <span class="d-block"><b>Current Offset:</b> {{ printParam(batt_monitor.aOff) }}</span>
      </div>
      <span class="d-block"><b>Low Voltage Failsafe:</b> {{ printParam(batt_failsafe_low.action) }}</span>
      <span
        v-if="batt_failsafe_low.level?.value"
        class="d-block"
      >
        <b>Low Voltage Level:</b> {{ printParam(batt_failsafe_low.level) }}
      </span>
      <span class="d-block"><b>Critical Voltage Failsafe:</b> {{ printParam(batt_failsafe_critical.action) }}</span>
      <span
        v-if="batt_failsafe_critical.level?.value"
        class="d-block"
      >
        <b>Low Voltage Level:</b> {{ printParam(batt_failsafe_low.level) }}
      </span>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import { printParam } from '@/types/autopilot/parameter'
import mavlink_store_get from '@/utils/mavlink'

// based on https://github.com/mavlink/qgroundcontrol/blob/Stable_V4.2/src/AutoPilotPlugins/APM/APMPowerComponent.qml
const power_modules_list = [
  {
    text: 'Power Module 90A',
    voltPin: 2,
    currPin: 3,
    voltMult: 10.1,
    ampPerVolt: 17.0,
    ampOffset: 0,
  },
  {
    text: 'Power Module HV',
    voltPin: 2,
    currPin: 3,
    voltMult: 12.02,
    ampPerVolt: 39.877,
    ampOffset: 0,
  },
  {
    text: '3DR Iris',
    voltPin: 2,
    currPin: 3,
    voltMult: 12.02,
    ampPerVolt: 17.0,
    ampOffset: 0,
  },
  {
    text: 'Blue Robotics Power Sense Module',
    voltPin: 2,
    currPin: 3,
    voltMult: 11.000,
    ampPerVolt: 37.8788,
    ampOffset: 0.330,
  }, {
    text: 'Navigator w/ Blue Robotics Power Sense Module',
    voltPin: 5,
    currPin: 4,
    voltMult: 11.000,
    ampPerVolt: 37.8788,
    ampOffset: 0.330,
  },
]

export default Vue.extend({
  name: 'PowerInfo',
  computed: {
    batt_failsafe_low() {
      return {
        action: autopilot_data.parameter('BATT_FS_LOW_ACT'),
        level: autopilot_data.parameter('BATT_LOW_VOLT'),
      }
    },
    batt_failsafe_critical() {
      return {
        action: autopilot_data.parameter('BATT_FS_CRT_ACT'),
        level: autopilot_data.parameter('BATT_CRT_VOLT'),
      }
    },
    batt_monitor() {
      const batt_monitor = autopilot_data.parameter('BATT_MONITOR')
      const batt_volt_pin = autopilot_data.parameter('BATT_VOLT_PIN')
      const batt_curr_pin = autopilot_data.parameter('BATT_CURR_PIN')
      const batt_volt_mult = autopilot_data.parameter('BATT_VOLT_MULT')
      const batt_curr_mult = autopilot_data.parameter('BATT_AMP_PERVLT')
      const batt_amp_offset = autopilot_data.parameter('BATT_AMP_OFFSET')
      return {
        monitor: batt_monitor,
        vPin: batt_volt_pin,
        aPin: batt_curr_pin,
        vMulti: batt_volt_mult,
        aPv: batt_curr_mult,
        aOff: batt_amp_offset,
      }
    },
    is_known_power_meter(): string | false {
      for (const entry of power_modules_list) {
        if (entry.voltPin === this.batt_monitor.vPin?.value
          && entry.currPin === this.batt_monitor.aPin?.value
          && entry.voltMult === this.batt_monitor.vMulti?.value
          && entry.ampPerVolt === this.batt_monitor.aPv?.value
          && entry.ampOffset === this.batt_monitor.aOff?.value) {
          return entry.text
        }
      }
      return false
    },
    battery_voltage(): string {
      const voltage_microvolts = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.voltage_battery') as number
      return (voltage_microvolts as number / 1000).toFixed(2)
    },

    battery_current(): string {
      const current_centiampere = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.current_battery') as number
      return (current_centiampere as number / 100).toFixed(2)
    },
  },
  methods: {
    printParam,
  },
})
</script>
