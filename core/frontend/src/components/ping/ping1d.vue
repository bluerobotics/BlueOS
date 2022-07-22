<template>
  <v-card style="min-width: 280px;">
    <v-card-title class="justify-center pb-1">
      <v-icon
        x-large
        class="ping1d"
        color="primary"
      >
        mdi-wifi
      </v-icon>
      {{ device.ping_type }}
    </v-card-title>
    <v-row class="justify-end">
      <v-btn
        icon
        class="pa-6"
        @click="show = !show"
      >
        <v-icon >{{ show ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
      </v-btn>
    </v-row>
    <v-expand-transition>
      <div v-show="show">
        <v-divider />
        <v-simple-table dense>
          <tbody>
            <tr>
              <td>Firmware</td><td>
                {{ `${device.firmware_version_major}.\
                ${device.firmware_version_minor}.\
                ${device.firmware_version_patch}` }}
              </td>
            </tr>
            <tr><td>ID</td><td>{{ device.device_id }}</td></tr>
            <tr><td>Model</td><td>{{ device.device_model }}</td></tr>
            <tr><td>Revision</td><td>{{ device.device_revision }}</td></tr>
            <tr><td>Device</td><td>{{ device.port }}</td></tr>
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
      </div>
    </v-expand-transition>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { PingDevice } from '@/types/ping'

export default Vue.extend({
  name: 'PingCard',
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
  },
})
</script>
<style scoped>
  i.ping1d {
    transform: rotate(180deg);
    margin: 15px;
  }
</style>
