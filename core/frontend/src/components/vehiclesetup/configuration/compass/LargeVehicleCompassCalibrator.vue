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
        Run Large Vehicle Calibration
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5 grey lighten-2">
        Large Vehicle Compass Calibration
      </v-card-title>
      <v-card-text>
        A Valid position is required for Compass Learn to estimate the local world magnetic field.
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
      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" :disabled="calibrating || !compass_mask" @click="calibrate()">
          Calibrate
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { PropType } from 'vue'

import StatusTextWatcher from '@/components/common/StatusTextWatcher.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import { deviceId } from '@/utils/deviceid_decoder'

export default {
  name: 'LargeVehicleCompassCalibrator',
  components: {
    StatusTextWatcher,
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
    },
    calirationFailed() {
      this.status_text = 'Calibration failed'
      this.status_type = 'error'
      this.calibrating = false
    },
    calibrate() {
      this.status_text = undefined
      this.calibrating = true
      this.largeVehicleCalibration(
        this.compass_mask,
        this.coordinates?.lat ?? 0,
        this.coordinates?.lon ?? 0,
      )
      // wait for a MAV_CMD_ACK message with result 0 (MAV_RESULT_ACCEPTED)
      const listener = mavlink2rest.startListening('COMMAND_ACK').setCallback((receivedMessage) => {
        if (receivedMessage.message.result.type === 'MAV_RESULT_ACCEPTED') {
          this.calibrationFinished()
        } else {
          this.calirationFailed()
        }
        listener.discard()
      })
    },
    largeVehicleCalibration(compass_mask: number, lat: number, lon: number) {
      mavlink2rest.sendMessage({
        header: {
          system_id: 255,
          component_id: 1,
          sequence: 1,
        },
        message: {
          type: 'COMMAND_LONG',
          param1: 0, // North
          param2: compass_mask,
          param3: parseInt(`${lat}`, 10),
          param4: parseInt(`${lon}`, 10),
          param5: 0,
          param6: 0,
          param7: 0,
          command: {
            type: MavCmd.MAV_CMD_FIXED_MAG_CAL_YAW,
          },
          target_system: autopilot_data.system_id,
          target_component: 1,
          confirmation: 0,
        },
      })
    },
  },
}
</script>

<style scoped>

</style>
