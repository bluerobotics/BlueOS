<template>
  <v-card class="pa-2">
    <v-card-title class="justify-center">
      Ping Sensors
    </v-card-title>
    <v-card-text class="d-flex justify-space-between">
      <v-card
        v-for="ping in pings"
        :key="ping.port"
        style="width: fit-content;"
      >
        <a href="/vehicle/pings">
          <v-img
            v-if="ping.ping_type === 'Ping1D'"
            v-tooltip="toText(ping)"
            :src="require('@/assets/img/ping/Ping1D.gif')"
            width="50px"
          />
          <v-img
            v-if="ping.ping_type === 'Ping360'"
            v-tooltip="toText(ping)"
            :src="require('@/assets/img/ping/Ping360.gif')"
            width="50px"
          />
        </a>
      </v-card>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import ping from '@/store/ping'
import { PingDevice } from '@/types/ping'

export default Vue.extend({
  name: 'PingInfo',
  computed: {
    pings() {
      return ping.available_ping_devices
    },
  },
  methods: {
    toText(device: PingDevice) {
      const mavlink_status = device.driver_status.mavlink_driver_enabled ? 'MAVLink enabled' : ''
      const port = device.driver_status.udp_port ? `listening at UDP ${device.driver_status.udp_port}` : ''
      const source = `${device.ping_type} at ${device.ethernet_discovery_info ?? ''}${device.port ?? ''}`
      return `${source}\n${mavlink_status}${port}`
    },
  },
})
</script>
<style scoped>
i.ping360 {
    transform: rotate(180deg);
    margin: 15px;
}
</style>
