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
import { getModule } from 'vuex-module-decorators'

import MavlinkStore from '@/store/mavlink'
import mavlink_store_get from '@/utils/mavlink'

const mavlink_store: MavlinkStore = getModule(MavlinkStore)

export default Vue.extend({
  name: 'HealthTrayMenu',
  components: {
  },

  computed: {
    cpu_temperature(): string {
      return 'WIP'
    },
    battery_voltage(): string {
      const voltage_microvolts = mavlink_store_get(mavlink_store, 'SYS_STATUS.messageData.voltage_battery') as number
      return (voltage_microvolts as number / 1000).toFixed(2)
    },

    battery_current(): string {
      const current_centiampere = mavlink_store_get(mavlink_store, 'SYS_STATUS.messageData.current_battery') as number
      return (current_centiampere as number / 100).toFixed(2)
    },
  },
})
</script>

<style>
</style>
