<template>
  <v-card style="min-width: 280px;">
    <v-card-title class="justify-center pb-1">
      <v-icon
        x-large
        class="ping1d"
        color="br_blue"
      >
        mdi-wifi
      </v-icon>
      {{ device.ping_type }}
    </v-card-title>
    <v-simple-table dense>
      <tbody>
        <tr><td>Bridge</td><td> UDP {{ device.driver_status.udp_port }} </td></tr>
        <tr
          v-tooltip="'Send MAVLink DISTANCE_SENSOR messages to the vehicle. This allows ground \
        stations such as QGroundControl to display the information on the telemetry overlay.'"
        >
          <td>MAVLink Distances</td><td>
            <v-switch
              v-model="user_desired_mavlink_driver_state"
              :loading="switch_loading() ? 'warning' : false"
              @change="update_mavlink_driver()"
            />
          </td>
        </tr>
      </tbody>
    </v-simple-table>
    <v-expand-transition>
      <div v-show="expand">
        <v-divider />
        <v-simple-table dense>
          <tbody>
            <tr>
              <td>FW</td><td>
                {{ format_version(device) }}
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
        icon
        class="pa-6"
        @click="expand = !expand"
      >
        <v-icon>{{ expand ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
      </v-btn>
    </v-row>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import DevicePathHelper from '@/components/common/DevicePathHelper.vue'
import { formatVersion, PingDevice } from '@/types/ping'
import back_axios from '@/utils/api'

export default Vue.extend({
  name: 'PingCard',
  components: {
    DevicePathHelper,
  },
  props: {
    device: {
      type: Object as PropType<PingDevice>,
      required: true,
    },
  },
  data() {
    return {
      expand: false,
      user_desired_mavlink_driver_state: true,
    }
  },
  computed: {
  },
  mounted() {
    this.user_desired_mavlink_driver_state = Boolean(this.device.driver_status.mavlink_driver_enabled)
  },
  methods: {
    format_version(device: PingDevice): string {
      return formatVersion(device)
    },
    switch_loading() {
      return this.user_desired_mavlink_driver_state !== Boolean(this.device.driver_status.mavlink_driver_enabled)
    },
    async update_mavlink_driver() {
      await back_axios({
        method: 'post',
        url: '/ping/v1.0/sensors',
        data: {
          port: this.device.port,
          mavlink_driver: this.user_desired_mavlink_driver_state,
        },
      })
    },
  },

})
</script>
<style scoped>
  i.ping1d {
    transform: rotate(180deg);
    margin: 15px;
  }
</style>
