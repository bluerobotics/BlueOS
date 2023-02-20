<template>
  <v-card style="min-width: 280px; min-height: 150px;">
    <v-card-title class="justify-center pb-1">
      <v-icon
        x-large
        class="ping360"
        color="br_blue"
      >
        mdi-radar
      </v-icon>
      {{ device.ping_type }}
    </v-card-title>
    <v-simple-table dense>
      <tbody>
        <tr><td>{{ is_ethernet() ? "IP" : "Bridge" }}</td><td> {{ ip_data() }} </td></tr>
      </tbody>
    </v-simple-table>
    <v-expand-transition
      v-if="!is_ethernet()"
    >
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
        v-if="!is_ethernet()"
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

export default Vue.extend({
  name: 'Ping360Card',
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
    }
  },
  computed: {
  },
  methods: {
    format_version(device: PingDevice): string {
      return formatVersion(device)
    },
    is_ethernet() {
      return this.device.ethernet_discovery_info !== null
    },
    ip_data() {
      if (this.is_ethernet()) {
        return this.device.ethernet_discovery_info
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
