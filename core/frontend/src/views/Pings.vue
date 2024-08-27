<template>
  <v-container>
    <div
      class="d-flex pa-5"
    >
      <div
        v-for="ping in ping_devices"
        :key="ping.device_id"
        class="pa-2"
        style="min-height: 100%;"
      >
        <ping-card
          v-if="ping.ping_type == PingType.Ping1D"
          :device="ping"
        />
        <ping-360-card
          v-if="ping.ping_type == PingType.Ping360"
          :device="ping"
        />
      </div>
      <v-container
        v-if="ping_devices.length === 0"
        class="text-center"
      >
        <p class="text-h6">
          No Ping devices available.
        </p>
      </v-container>
    </div>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import { OneMoreTime } from '@/one-more-time'
import ping from '@/store/ping'
import system_information from '@/store/system-information'
import { PingDevice, PingType } from '@/types/ping'

import PingCard from '../components/ping/ping1d.vue'
import Ping360Card from '../components/ping/ping360.vue'

export default Vue.extend({
  name: 'Pings',
  components: { PingCard, Ping360Card },
  data: () => ({
    PingType,
    fetch_serial_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
  }),
  computed: {
    ping_devices(): PingDevice[] {
      return ping.available_ping_devices
    },
  },
  mounted() {
    ping.registerObject(this)
    this.fetch_serial_task.setAction(system_information.fetchSerial)
  },
})
</script>

<style scoped>
  .v-card {
    padding: 10px;
  }
</style>
