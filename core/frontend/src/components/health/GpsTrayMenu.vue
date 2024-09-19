<template>
  <v-menu
    :close-on-content-click="false"
    nudge-left="275"
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
        <v-badge
          v-if="gps_connected"
          :content="satellites_number"
          :value="satellites_number"
          :title="`${connection_description} (Number of satellites: ${satellites_number})`"
          :color="number_color"
          :dot="!mouse_hover"
          v-bind="attrs"
          class="mr-2"
          overlap
          v-on="on"
        >
          <v-icon
            color="white"
            @mouseover="mouse_hover = true"
            @mouseleave="mouse_hover = false"
          >
            mdi-satellite-variant
          </v-icon>
        </v-badge>
      </v-card>
    </template>
    <v-card
      elevation="1"
      width="275"
    >
      <v-container>
        <div>
          <table
            v-for="(item, index) in values"
            :key="`${item.name}-${index}`"
            style="width: 100%"
          >
            <tr v-tooltip="item.tooltip">
              <td>
                <v-icon
                  size="large"
                  v-text="item.icon"
                />
                {{ item.name }}:
              </td>
              <td class="value">
                {{ item.value }}
                <v-btn
                  v-if="item?.link"
                  width="18"
                  class="mr-0 pr-0 ml-1"
                  icon
                  :href="item.link"
                  target="_blank"
                >
                  <v-icon size="x-large" color="primary">
                    {{ item.link_icon }}
                  </v-icon>
                </v-btn>
              </td>
            </tr>
          </table>
        </div>
      </v-container>
    </v-card>
  </v-menu>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { GpsFixType } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import {
  GlobalPositionInt,
  Gps2Raw,
  GpsRawInt,
} from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message'
import autopilot_data from '@/store/autopilot'

export default Vue.extend({
  name: 'GpsTrayMenu',
  props: {
    instance: {
      type: Number,
      required: true,
    },
  },
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
    values():
      Array<
        {
          name: string,
          value: string,
          tooltip?: string,
          icon: string,
          link?: string,
          link_icon?: string
        }> {
      if (!this.gps_raw_int) {
        return []
      }
      const values = [
        {
          name: 'Position',
          value: `${this.latitude.toFixed(2)}º / ${this.longitude.toFixed(2)}º`,
          tooltip: 'Position coordinates',
          icon: 'mdi-map-marker',
          link: this.map_link,
          link_icon: 'mdi-map-search',
        },
        {
          name: 'Altitude',
          value: `${(this.gps_raw_int.alt / 1000).toFixed(2)} m`,
          tooltip: 'Altitude estimate',
          icon: 'mdi-arrow-collapse-up',
        },
        {
          name: 'Satellites',
          value: `${this.satellites_number}`,
          tooltip: 'Satellites in view',
          icon: 'mdi-satellite-variant',
        },
        {
          name: 'Fix',
          value: `${this.connection_description}`,
          tooltip: 'Connection type and status',
          icon: 'mdi-crosshairs-gps',
        },
        {
          name: 'HDOP',
          value: `${(this.gps_raw_int.eph / 100).toFixed(2)}`,
          tooltip: 'Horizontal position uncertainty',
          icon: 'mdi-arrow-left-right',
        },
        {
          name: 'VDOP',
          value: `${(this.gps_raw_int.epv / 100).toFixed(2)}`,
          tooltip: 'Vertical position uncertainty',
          icon: 'mdi-arrow-up-down',
        },
        {
          name: 'PDOP',
          value: `${(((this.gps_raw_int.epv / 100) ** 2 + (this.gps_raw_int.eph / 100) ** 2) ** 0.5).toFixed(2)}`,
          tooltip: 'Combined 3D position uncertainty',
          icon: 'mdi-map-marker-radius',
        },
      ]

      if (this.gps_raw_int?.h_acc) {
        values.push(
          {
            name: 'HACC',
            value: `${(this.gps_raw_int.h_acc / 1000).toFixed(2)} m`,
            tooltip: 'Horizontal Accuracy',
            icon: 'mdi-arrow-expand-horizontal',
          },
          {
            name: 'VACC',
            value: `${(this.gps_raw_int.v_acc / 1000).toFixed(2)} m`,
            tooltip: 'Vertical Accuracy',
            icon: 'mdi-arrow-expand-vertical',
          },
        )
      }
      if (this.gps_raw_int?.yaw !== 0) {
        values.push(
          {
            name: 'Yaw',
            value: `${(this.gps_raw_int.yaw / 100).toFixed(2)}º`,
            tooltip: 'Yaw',
            icon: 'mdi-compass',
          },
        )
      }

      return values
    },
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
    latitude(): number {
      return (this.gps_raw_int?.lat ?? 0) / 1E7
    },
    longitude(): number {
      return (this.gps_raw_int?.lon ?? 0) / 1E7
    },
    map_link(): string {
      const zoom = 16
      const marker = `lat=${this.latitude}&lon=${this.longitude}`
      const map = `${zoom}/${this.latitude}/${this.longitude}&layers=N`
      return `https://www.openstreetmap.org/note/new?${marker}#map=${map}`
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

    const message_name = this.instance === 1 ? 'GPS_RAW_INT' : 'GPS2_RAW'
    mavlink2rest.startListening(message_name).setCallback((message) => {
      if (message?.header.system_id !== autopilot_data.system_id || message?.header.component_id !== 1) {
        return
      }

      this.last_message_date = new Date()
      this.gps_raw_int = message?.message as GpsRawInt | Gps2Raw
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

.value {
  text-align: right;
}
</style>
