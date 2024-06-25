<template>
  <v-badge
    v-if="gps_connected"
    :content="satellites_number"
    :value="satellites_number"
    :title="`${connection_description} (Number of satellites: ${satellites_number})`"
    :color="number_color"
    :dot="!mouse_hover"
    class="mr-2"
    overlap
  >
    <v-icon
      color="white"
      @mouseover="mouse_hover = true"
      @mouseleave="mouse_hover = false"
    >
      mdi-satellite-variant
    </v-icon>
  </v-badge>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { GpsFixType } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import { GlobalPositionInt, GpsRawInt } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message'
import autopilot_data from '@/store/autopilot'

export default Vue.extend({
  name: 'GpsTrayMenu',
  data() {
    return {
      mouse_hover: false,
      time_limit_message: 20000,
      last_message_date: undefined as undefined | Date,
      gps_detected: false,
      global_position_int: undefined as undefined | GlobalPositionInt,
      gps_raw_int: undefined as undefined | GpsRawInt,
    }
  },
  computed: {
    gps_connected(): boolean {
      if (this.last_message_date === undefined) {
        return false
      }

      if (this.last_message_date.getTime() + this.time_limit_message < new Date().getTime()) {
        return false
      }

      return this.gps_detected
    },
    connection_description(): string {
      switch (this.gps_raw_int?.fix_type?.type) {
        case GpsFixType.GPS_FIX_TYPE_NO_GPS:
          return 'No GPS connection'
        case GpsFixType.GPS_FIX_TYPE_NO_FIX:
          return 'GPS connected, but no position fix'
        case GpsFixType.GPS_FIX_TYPE_2D_FIX:
          return '2D GPS fix'
        case GpsFixType.GPS_FIX_TYPE_3D_FIX:
          return '3D GPS fix'
        case GpsFixType.GPS_FIX_TYPE_DGPS:
          return 'DGPS/SBAS aided 3D position'
        case GpsFixType.GPS_FIX_TYPE_RTK_FLOAT:
          return 'RTK float, 3D position'
        case GpsFixType.GPS_FIX_TYPE_RTK_FIXED:
          return 'RTK fixed, 3D position'
        case GpsFixType.GPS_FIX_TYPE_STATIC:
          return 'Static fixed, 3D position'
        case GpsFixType.GPS_FIX_TYPE_PPP:
          return 'PPP, 3D position'
        default:
          return 'Unknown'
      }
    },
    number_color(): string {
      switch (this.gps_raw_int?.fix_type?.type) {
        case GpsFixType.GPS_FIX_TYPE_NO_FIX:
          return 'warning'
        case GpsFixType.GPS_FIX_TYPE_2D_FIX:
          return 'warning'
        case GpsFixType.GPS_FIX_TYPE_3D_FIX:
        case GpsFixType.GPS_FIX_TYPE_DGPS:
        case GpsFixType.GPS_FIX_TYPE_RTK_FLOAT:
        case GpsFixType.GPS_FIX_TYPE_RTK_FIXED:
        case GpsFixType.GPS_FIX_TYPE_STATIC:
        case GpsFixType.GPS_FIX_TYPE_PPP:
          return 'success'
        default:
          return 'error'
      }
    },
    satellites_number(): number {
      return this.gps_raw_int?.satellites_visible || 0
    },
  },
  mounted() {
    mavlink2rest.startListening('GLOBAL_POSITION_INT').setCallback((message) => {
      if (message?.header.system_id !== autopilot_data.system_id || message?.header.component_id !== 1) {
        return
      }

      this.last_message_date = new Date()
      this.global_position_int = message?.message as GlobalPositionInt
    }).setFrequency(0)

    mavlink2rest.startListening('GPS_RAW_INT').setCallback((message) => {
      if (message?.header.system_id !== autopilot_data.system_id || message?.header.component_id !== 1) {
        return
      }

      this.last_message_date = new Date()
      this.gps_raw_int = message?.message as GpsRawInt
      this.gps_detected = this.gps_raw_int?.fix_type?.type !== GpsFixType.GPS_FIX_TYPE_NO_GPS
    }).setFrequency(0)
  },
})
</script>

<style scoped>
div.number-marker {
  position: relative;
  top: -10px;
  right: -20px;
  width: 15px;
  height: 15px;
  opacity: 0.7;
}

div.number-marker.v-icon {
  font-size: 10px;
}
</style>
