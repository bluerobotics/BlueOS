<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="150"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-card
        elevation="0"
        color="transparent"
        v-bind="attrs"
        v-on="on"
      >
        <v-icon
          class="px-1"
          color="white"
        >
          mdi-heart-pulse
        </v-icon>
      </v-card>
    </template>

    <v-card
      elevation="1"
      width="250"
    >
      <v-container>
        <div>
          <table style="width: 100%">
            <tr>
              <td>Core Temperature:</td>
              <td>{{ cpu_temperature }} ºC</td>
            </tr>
            <tr>
              <td>Voltage:</td>
              <td>{{ battery_voltage }} V</td>
            </tr>
            <tr>
              <td>Current:</td>
              <td> {{ battery_current }} A</td>
            </tr>
          </table>
        </div>
      </v-container>
    </v-card>
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink from '@/store/mavlink'
import system_information from '@/store/system-information'
import mavlink_store_get from '@/utils/mavlink'

export default Vue.extend({
  name: 'HealthTrayMenu',
  computed: {
    cpu_temperature(): string {
      const temperature_sensors = system_information.system?.temperature
      const main_sensor = temperature_sensors?.find((sensor) => sensor.name === 'CPU')
      return main_sensor ? main_sensor.temperature.toFixed(1) : 'Loading..'
    },
    battery_voltage(): string {
      const voltage_microvolts = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.voltage_battery') as number
      return (voltage_microvolts as number / 1000).toFixed(2)
    },

    battery_current(): string {
      const current_centiampere = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.current_battery') as number
      return (current_centiampere as number / 100).toFixed(2)
    },
  },
})
</script>

<style>
</style>
