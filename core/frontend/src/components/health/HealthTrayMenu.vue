<template>
  <v-row style="display: contents;">
    <v-icon
      v-if="disk_usage_high"
      v-tooltip="`High disk usage! (${disk_usage_percent.toFixed(1)}%) please clean up the disk`"
      class="px-1 blinking white-shadow"
      color="red"
      @click="$router.push('/tools/disk')"
    >
      mdi-content-save-alert
    </v-icon>
    <v-icon
      v-if="cpu_temperature_limit_reached"
      class="px-1 blinking white-shadow"
      color="error"
      :title="`CPU temperature too high (${cpu_temperature} ºC), please cool down your vehicle!`"
    >
      mdi-thermometer
    </v-icon>
    <v-icon
      v-if="cpu_throttled"
      class="px-1 blinking white-shadow"
      color="error"
      :title="`CPU is throttled. Performance may be affected. Please check your power supply and cooling!`"
    >
      mdi-gauge-empty
    </v-icon>
    <v-icon
      v-if="cpu_undervoltage"
      class="px-1 blinking white-shadow"
      color="error"
      :title="`CPU has reported low voltage. Please check your power supply!`"
    >
      mdi-lightning-bolt
    </v-icon>
    <v-menu
      :close-on-content-click="false"
      nudge-left="150"
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
          <v-icon
            v-if="heartbeat_age() < time_limit_heartbeat"
            class="px-1"
            :color="heartbeat_color()"
            :title="heartbeat_message()"
          >
            mdi-heart-pulse
          </v-icon>
          <v-icon
            v-if="heartbeat_age() >= time_limit_heartbeat"
            class="px-1 white-shadow"
            color="error"
            title="MAVLink heartbeat lost"
          >
            mdi-heart-broken
          </v-icon>
        </v-card>
      </template>

      <v-card
        elevation="1"
        width="250"
      >
        <v-container>
          <div>
            <table style="width: 100%">
              <tr>
                <td>Core Temperature:</td>
                <td>{{ cpu_temperature }} ºC</td>
              </tr>
              <tr>
                <td>Voltage:</td>
                <td>{{ battery_voltage }} V</td>
              </tr>
              <tr>
                <td>Current:</td>
                <td> {{ battery_current }} A</td>
              </tr>
              <tr v-for="(calibrated, sensor_name,) in ardupilot_sensors.sensors" :key="sensor_name">
                <td class="sensor-type">
                  {{ sensor_name }}:
                </td>
                <td v-if="!calibrated">
                  <v-btn
                    x-small
                    :to="{ name: 'Vehicle Setup', params: { tab: 'configure', subtab: sensor_name } }"
                    color="primary"
                  >
                    Calibrate
                  </v-btn>
                </td>
                <td v-else>
                  Calibrated
                </td>
              </tr>
            </table>
          </div>
        </v-container>
      </v-card>
    </v-menu>
  </v-row>
</template>

<script lang="ts">
import Vue from 'vue'

import { convertHexToRgbd } from '@/cosmos'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavModeFlag, MavType } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import ardupilot_sensors, { ArdupilotSensorsStore } from '@/store/ardupilot_sensors'
import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import system_information from '@/store/system-information'
import * as DEFAULT_COLORS from '@/style/colors/default'
import { RaspberryEventType } from '@/types/system-information/platform'
import { Disk } from '@/types/system-information/system'
import mavlink_store_get from '@/utils/mavlink'

export default Vue.extend({
  name: 'HealthTrayMenu',
  data() {
    return {
      time_limit_heartbeat: 3000,
    }
  },
  computed: {
    cpu_temperature(): string {
      const temperature_sensors = system_information.system?.temperature
      const main_sensor = temperature_sensors?.find(
        (sensor) => sensor.name.toLowerCase().includes('cpu') || sensor.name.toLowerCase().includes('soc'),
      )
      return main_sensor ? main_sensor.temperature.toFixed(1) : 'Loading..'
    },
    cpu_throttled() : boolean {
      const events = system_information.platform?.raspberry?.events
      const throttling = events?.occurring?.find((event) => [
        RaspberryEventType.FrequencyCapping,
        RaspberryEventType.Throttling,
      ].includes(event.type))
      return throttling !== undefined
    },
    cpu_undervoltage() : boolean {
      const events = system_information.platform?.raspberry?.events
      const undervoltage = events?.occurring?.find((event) => event.type === RaspberryEventType.UnderVoltage)
      return undervoltage !== undefined
    },
    cpu_temperature_limit_reached() : boolean {
      const events = system_information.platform?.raspberry?.events
      const temperature_limit = events?.occurring?.find((event) => event.type === RaspberryEventType.TemperatureLimit)
      return temperature_limit !== undefined
    },
    battery_voltage(): string {
      const voltage_microvolts = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.voltage_battery') as number
      return (voltage_microvolts as number / 1000).toFixed(2)
    },

    battery_current(): string {
      const current_centiampere = mavlink_store_get(mavlink, 'SYS_STATUS.messageData.message.current_battery') as number
      return (current_centiampere as number / 100).toFixed(2)
    },
    main_disk(): undefined | Disk {
      const disks = system_information.system?.disk
      return disks?.find((sensor) => sensor.mount_point === '/')
    },
    disk_usage_percent(): number {
      return this.main_disk ? 100 - this.main_disk.available_space_B / this.main_disk.total_space_B / 0.01 : 0
    },
    disk_usage_high(): boolean {
      return this.disk_usage_percent > 85
    },
    ardupilot_sensors(): ArdupilotSensorsStore {
      return ardupilot_sensors
    },
  },
  mounted() {
    mavlink2rest.startListening('HEARTBEAT').setCallback((message) => {
      if (!this.is_vehicle(message?.message.mavtype.type) || message?.header.component_id !== 1) {
        return
      }
      autopilot_data.setSystemId(message?.header.system_id)
      autopilot_data.setAutopilotType(message?.message.autopilot.type)
      autopilot_data.setVehicleArmed(Boolean(message?.message.base_mode.bits & MavModeFlag.MAV_MODE_FLAG_SAFETY_ARMED))
      autopilot_data.setLastHeartbeatDate(new Date())
    }).setFrequency(0)
  },
  methods: {
    heartbeat_age(): number {
      return new Date().valueOf() - autopilot_data.last_heartbeat_date.getTime()
    },
    is_vehicle(type: string) {
      return [
        MavType.MAV_TYPE_FIXED_WING,
        MavType.MAV_TYPE_VTOL_DUOROTOR,
        MavType.MAV_TYPE_VTOL_QUADROTOR,
        MavType.MAV_TYPE_VTOL_TILTROTOR,
        MavType.MAV_TYPE_VTOL_RESERVED4,
        MavType.MAV_TYPE_VTOL_RESERVED5,
        MavType.MAV_TYPE_QUADROTOR,
        MavType.MAV_TYPE_COAXIAL,
        MavType.MAV_TYPE_HELICOPTER,
        MavType.MAV_TYPE_HEXAROTOR,
        MavType.MAV_TYPE_OCTOROTOR,
        MavType.MAV_TYPE_TRICOPTER,
        MavType.MAV_TYPE_GROUND_ROVER,
        MavType.MAV_TYPE_SURFACE_BOAT,
        MavType.MAV_TYPE_SUBMARINE,
        // The next two ones are not defined?
        'MAV_TYPE_VTOL_FIXEDROTOR',
        'MAV_TYPE_VTOL_TAILSITTER',
      ].includes(type)
    },
    heartbeat_color() : string {
      const selected_color = ardupilot_sensors.all_sensors_calibrated
        ? DEFAULT_COLORS.SHEET_LIGHT_BG : DEFAULT_COLORS.WARNING
      const [r, g, b] = convertHexToRgbd(selected_color)
      const opacity = Math.max(0.4, 1.4 - this.heartbeat_age() / 1000)

      return `rgba(${r}, ${g}, ${b}, ${opacity})`
    },
    heartbeat_message() : string {
      if (ardupilot_sensors.all_sensors_calibrated) {
        return 'MAVLink heartbeats arriving as expected'
      }
      return 'One or more sensors are not calibrated'
    },
  },
})
</script>

<style>
.blinking {
  animation: blinker 1s linear infinite;
}
@keyframes blinker {
  50% {
    opacity: 0.5;
  }
}

.white-shadow {
  text-shadow: 0 0 3px #FFF;
}

.sensor-type {
  text-transform: capitalize;
}
</style>
