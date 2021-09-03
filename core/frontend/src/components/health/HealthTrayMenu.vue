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
          mdi-submarine
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
              <td>-- ºC</td>
            </tr>
            <tr>
              <td>Voltage:</td>
              <td>{{ batt_voltage.toFixed(2) }} V</td>
            </tr>
            <tr>
              <td>Current:</td>
              <td> {{ batt_current.toFixed(2) }} A</td>
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

const mavlink_store: MavlinkStore = getModule(MavlinkStore)

export default Vue.extend({
  name: 'HealthTrayMenu',
  components: {
  },

  computed: {
    batt_voltage(): number {
      if (mavlink_store.available_messages.SYS_STATUS) {
        const data = mavlink_store.available_messages.SYS_STATUS.messageData.voltage_battery
        if (typeof data === 'number') {
          return data / 1000
        }
      }
      return -1
    },

    batt_current(): number {
      if (mavlink_store.available_messages.SYS_STATUS) {
        const data = mavlink_store.available_messages.SYS_STATUS.messageData.current_battery
        if (typeof data === 'number') {
          return data / 100
        }
      }
      return -1
    },
  },

  mounted() {
    mavlink_store.setMessageRefreshRate({
      message: 'SYS_STATUS',
      refreshRate: 3,
    })
  },
})
</script>

<style>
</style>
