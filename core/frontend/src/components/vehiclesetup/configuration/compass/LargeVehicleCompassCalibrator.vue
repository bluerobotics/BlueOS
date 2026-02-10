<template>
  <v-dialog
    v-model="dialog"
    width="600"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        v-bind="attrs"
        v-on="on"
      >
        Start Large Vehicle Calibration
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5 grey lighten-2 black--text">
        Large Vehicle Compass Calibration
      </v-card-title>
      <v-card-text>
        A valid global region/position is required to estimate the local world magnetic field.
        <auto-coordinate-detector
          v-model="coordinates"
        />
        <compass-mask-picker v-model="compass_mask" :devices="compasses" />
        <v-divider />
        <v-alert
          v-if="status_text"
          :type="status_type"
        >
          {{ status_text }}
        </v-alert>
        <StatusTextWatcher :style="`display : ${status_type === 'error' ? 'block' : 'none'};`" />
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn color="primary" :disabled="calibrating || !compass_mask || !coordinates" @click="calibrate()">
          Calibrate
        </v-btn>
        <reboot-button />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { PropType } from 'vue'

import StatusTextWatcher from '@/components/common/StatusTextWatcher.vue'
import RebootButton from '@/components/utils/RebootButton.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd, MavResult } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import { deviceId } from '@/utils/deviceid_decoder'

export default {
  name: 'LargeVehicleCompassCalibrator',
  components: {
    StatusTextWatcher,
    RebootButton,
  },
  props: {
    compasses: {
      type: Array as PropType<deviceId[]>,
      required: true,
    },
  },
  data() {
    return {
      dialog: false,
      coordinates: undefined as { lat: number, lon: number } | undefined,
      compass_mask: 0,
      calibrating: false,
      status_type: '' as string | undefined,
      status_text: '' as string | undefined,
    }
  },
  methods: {
    calibrationFinished() {
      this.status_type = 'success'
      this.status_text = 'Calibration finished'
      this.calibrating = false
      autopilot_data.setRebootRequired(true)
    },
    calibrationFailed(error: string) {
      this.status_text = `Calibration failed: ${error}`
      this.status_type = 'error'
      this.calibrating = false
    },
    async calibrate() {
      this.status_text = undefined
      this.calibrating = true
      this.largeVehicleCalibration(
        this.compass_mask,
        this.coordinates?.lat ?? 0,
        this.coordinates?.lon ?? 0,
      )
      // wait for a MAV_CMD_ACK message with result 0 (MAV_RESULT_ACCEPTED)
      try {
        const ack = await mavlink2rest.waitForAck(MavCmd.MAV_CMD_FIXED_MAG_CAL_YAW)
        if (ack.result.type !== MavResult.MAV_RESULT_ACCEPTED) {
          throw new Error(`Unexpected result: ${ack.result.type}`)
        }
        this.calibrationFinished()
      } catch (error) {
        this.calibrationFailed(`${error}`)
      }
    },
    largeVehicleCalibration(compass_mask: number, lat: number, lon: number) {
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_FIXED_MAG_CAL_YAW,
        0, // North
        compass_mask,
        parseInt(`${lat}`, 10),
        parseInt(`${lon}`, 10),
      )
    },
  },
}
</script>
