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
    </div>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import ping from '@/store/ping'
import { PingDevice, PingType } from '@/types/ping'

import PingCard from '../components/ping/ping1d.vue'
import Ping360Card from '../components/ping/ping360.vue'

export default Vue.extend({
  name: 'Pings',
  components: { PingCard, Ping360Card },
  data: () => ({
    PingType,
  }),
  computed: {
    ping_devices(): PingDevice[] {
      return ping.available_ping_devices
    },
  },
  mounted() {
    ping.registerObject(this)
  },
})
</script>

<style scoped>
  .v-card {
    padding: 10px;
  }
</style>
