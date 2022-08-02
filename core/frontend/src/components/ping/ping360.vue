<template>
  <v-card style="min-width: 280px;">
    <v-card-title class="justify-center pb-1">
      <v-icon
        x-large
        class="ping360"
        color="primary"
      >
        mdi-radar
      </v-icon>
      {{ device.ping_type }}
    </v-card-title>
    <v-simple-table dense>
      <tbody>
        <tr><td>{{ is_ethernet ? "IP" : "Bridge" }}</td><td> {{ ip_data() }} </td></tr>
      </tbody>
    </v-simple-table>
    <v-expand-transition
      v-if="!is_ethernet()"
    >
      <div v-show="show">
        <v-divider />
        <v-simple-table dense>
          <tbody>
            <tr>
              <td>FW</td><td>
                {{ device.firmware_version_major }}.
                {{ device.firmware_version_minor }}.
                {{ device.firmware_version_patch }}
              </td>
            </tr>
            <tr><td>ID</td><td>{{ device.device_id }}</td></tr>
            <tr><td>Model</td><td>{{ device.device_model }}</td></tr>
            <tr><td>Revision</td><td>{{ device.device_revision }}</td></tr>
            <tr><td>Device</td><td>{{ device.port }} <device-path-helper :device="device.port" /></td></tr>
          </tbody>
        </v-simple-table>
      </div>
    </v-expand-transition>

    <v-row class="justify-end">
      <v-btn
        v-if="!is_ethernet()"
        icon
        class="pa-6"
        @click="show = !show"
      >
        <v-icon>{{ show ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
      </v-btn>
    </v-row>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { PingDevice } from '@/types/ping'

export default Vue.extend({
  name: 'Ping360Card',
  props: {
    device: {
      type: Object as PropType<PingDevice>,
      required: true,
    },
  },
  data() {
    return {
      show: false,
    }
  },
  computed: {
  },
  methods: {
    is_ethernet() {
      return this.device.ethernet_info !== ''
    },
    ip_data() {
      if (this.is_ethernet()) {
        return this.device.ethernet_info
      }
      return `UDP ${this.device.driver_status.udp_port}`
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
