<template>
  <v-dialog
    v-model="dialog"
    width="500"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        class="ma-2"
        v-bind="attrs"
        v-on="on"
      >
        Quick Calibration
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5">
        Accelerometer Calibration
      </v-card-title>
      <v-card-text>
        <div>
          Quick calibration requires that you place the vehicle on a level surface and keep it still for a few seconds.
          It is usually enough if your vehicle is generally leveled while in use.
        </div>
      </v-card-text>
      <v-card-actions>
        <v-alert v-if="state === states.CALIBRATED" type="success">
          Calibration Successful
        </v-alert>
        <v-btn v-if="state === states.IDLE" class="primary" @click="doCalibration">
          Start Calibration
        </v-btn>
        <SpinningLogo v-if="state === states.CALIBRATION_STARTED" size="15%" />
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'

const states = {
  IDLE: 0,
  WAITING_FOR_RESPONSE: 1,
  CALIBRATION_STARTED: 2,
  CALIBRATED: 3,
}

export default {
  name: 'QuickAccelerometerCalibration',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      dialog: false,
      calibrating: false,
      state: states.IDLE,
    }
  },
  computed: {
    states() {
      return states
    },
  },
  methods: {
    doCalibration() {
      this.calibrating = true
      mavlink2rest.sendMessage({
        header: {
          system_id: 255,
          component_id: 1,
          sequence: 1,
        },
        message: {
          type: 'COMMAND_LONG',
          param1: 0,
          param2: 0,
          param3: 0,
          param4: 0,
          param5: 4, // see https://mavlink.io/en/messages/common.html#MAV_CMD_PREFLIGHT_CALIBRATION
          param6: 0,
          param7: 0,
          command: {
            type: MavCmd.MAV_CMD_PREFLIGHT_CALIBRATION,
          },
          target_system: autopilot_data.system_id,
          target_component: 1,
          confirmation: 1,
        },
      })
      this.state = states.WAITING_FOR_RESPONSE
      let timeout = 0
      this.state = states.CALIBRATION_STARTED
      const ack_listener = mavlink2rest.startListening('COMMAND_ACK').setCallback((message) => {
        if (message?.message?.command?.type === 'MAV_CMD_PREFLIGHT_CALIBRATION') {
          if (message.message.result.type !== 'MAV_RESULT_ACCEPTED') {
            console.error(
              `Unexpected answer to quick accel calibration: ${message.result.type}`,
            )
          }
          clearTimeout(timeout)
          this.state = states.CALIBRATED
          ack_listener.discard()
          setTimeout(() => { this.dialog = false }, 2000)
          setTimeout(() => { this.state = states.IDLE }, 3000)
        }
      })
      timeout = setTimeout(() => {
        ack_listener.discard()
        this.state = states.IDLE
        this.dialog = false
      }, 5000)
    },
  },
}
</script>
