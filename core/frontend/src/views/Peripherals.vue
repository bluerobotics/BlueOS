<template>
  <v-container>
    <div
      class="d-flex pa-5"
    >
      <v-card
        v-for="ping in ping_devices"
        :key="ping.device_id"
        class="pa-2"
        style="min-height: 100%;"
      >
        <v-card-title class="justify-center">
          {{ ping.ping_type }}
        </v-card-title>
        <v-simple-table dense>
          <tbody>
            <tr>
              <td>Firmware</td><td>
                {{ `${ping.firmware_version_major}.${ping.firmware_version_minor}.${ping.firmware_version_patch}` }}
              </td>
            </tr>
            <tr><td>ID</td><td>{{ ping.device_id }}</td></tr>
            <tr><td>Model</td><td>{{ ping.device_model }}</td></tr>
            <tr><td>Revision</td><td>{{ ping.device_revision }}</td></tr>
            <tr><td>Device</td><td>{{ ping.port }}</td></tr>
            <tr><td>Bridge</td><td> N/A </td></tr>
            <tr>
              <td>Mavlink Driver</td><td>
                <v-switch
                  inset
                  disabled
                />
              </td>
            </tr>
          </tbody>
        </v-simple-table>
      </v-card>
    </div>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import ping from '@/store/ping'
import { PingDevice } from '@/types/ping'

export default Vue.extend({
  name: 'Peripherals',
  data: () => ({
  }),
  computed: {
    ping_devices(): PingDevice[] {
      return ping.available_ping_devices
    },
  },
})
</script>

<style scoped>
  .v-card {
    padding: 20px;
  }
</style>
