<template>
  <v-dialog
    v-model="dialog"
    :persistent="!show_ok_button && !show_next_button && !show_start_button"
    width="500"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        class="ma-2"
        v-bind="attrs"
        v-on="on"
      >
        Start Full Calibration
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5">
        Accelerometer Calibration
      </v-card-title>
      <div class="ma-6">
        <p>
          Full accelerometer calibration requires you to place the vehicle onto all of its sides and keep
          it still for a few seconds.
          This will allow the autopilot to calibrate the accelerometer.
        </p>
      </div>
      <v-alert
        v-if="![states.IDLE, states.WAITING_FOR_VEHICLE_RESPONSE].includes(state)"
        dense
        :type="current_state_type"
      >
        <strong>{{ current_state_text }}</strong>
      </v-alert>
      <generic-viewer
        :autorotate="false"
        :transparent="false"
        :cameracontrols="false"
        :orientation="current_state_3D"
      />
      <v-card-actions class="justify-center">
        <v-btn v-if="show_start_button" :loading="start_button_loading" class="primary" @click="startCalibration">
          Start Calibration
        </v-btn>
        <v-btn v-if="show_next_button" class="primary" @click="nextStep">
          Next
        </v-btn>
        <v-btn v-if="show_ok_button" class="primary" @click="cleanup">
          Ok
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">

import GenericViewer from '@/components/vehiclesetup/viewers/GenericViewer.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'

import { calibrator, PreflightCalibration } from '../../calibration'

// Ideally these would come from mavlink2rest-enum
// but we don't have the numbering information there
enum AccelcalVehiclePos {
  ACCELCAL_VEHICLE_POS_LEVEL = 1,
  ACCELCAL_VEHICLE_POS_LEFT = 2,
  ACCELCAL_VEHICLE_POS_RIGHT = 3,
  ACCELCAL_VEHICLE_POS_NOSEDOWN = 4,
  ACCELCAL_VEHICLE_POS_NOSEUP = 5,
  ACCELCAL_VEHICLE_POS_BACK = 6,
  ACCELCAL_VEHICLE_POS_SUCCESS = 16777215,
  ACCELCAL_VEHICLE_POS_FAILED = 16777216
}

enum CalState {
  IDLE,
  WAITING_FOR_VEHICLE_RESPONSE,
  WAITING_FOR_LEVEL_POSITION,
  WAITING_FOR_LEFT_POSITION,
  WAITING_FOR_RIGHT_POSITION,
  WAITING_FOR_NOSEDOWN_POSITION,
  WAITING_FOR_NOSEUP_POSITION,
  WAITING_FOR_BACK_POSITION,
  SUCCESS,
  FAIL,
}

export default {
  name: 'FullAccelerometerCalibration',
  components: {
    GenericViewer,
  },
  data() {
    return {
      dialog: false,
      state: CalState.IDLE,
    }
  },
  computed: {
    states() {
      return CalState
    },
    show_next_button() {
      return ![
        CalState.IDLE,
        CalState.FAIL,
        CalState.SUCCESS,
        CalState.WAITING_FOR_VEHICLE_RESPONSE,
      ].includes(this.state)
    },
    show_ok_button() {
      return [CalState.SUCCESS, CalState.FAIL].includes(this.state)
    },
    show_start_button() {
      return [CalState.IDLE, CalState.WAITING_FOR_VEHICLE_RESPONSE].includes(this.state)
    },
    start_button_loading() {
      return this.state === CalState.WAITING_FOR_VEHICLE_RESPONSE
    },
    current_state_text() {
      const AccelStateText: { [key: number]: string } = {
        [CalState.WAITING_FOR_LEVEL_POSITION]: 'Place the vehicle on a level surface',
        [CalState.WAITING_FOR_LEFT_POSITION]: 'Place the vehicle on its left side',
        [CalState.WAITING_FOR_RIGHT_POSITION]: 'Place the vehicle on its right side',
        [CalState.WAITING_FOR_NOSEDOWN_POSITION]: 'Place the vehicle with its nose down',
        [CalState.WAITING_FOR_NOSEUP_POSITION]: 'Place the vehicle with its nose up',
        [CalState.WAITING_FOR_BACK_POSITION]: 'Place the vehicle on its back',
        [CalState.SUCCESS]: 'Calibration Successful',
        [CalState.FAIL]: 'Calibration Failed',
      }
      return AccelStateText[Number(this.state)] ?? 'Unknown state'
    },
    current_state_3D() {
      const AccelStateText: { [key: number]: string } = {
        [CalState.WAITING_FOR_LEVEL_POSITION]: '0deg 0deg 0deg',
        [CalState.WAITING_FOR_LEFT_POSITION]: '-90deg 0deg 0deg',
        [CalState.WAITING_FOR_RIGHT_POSITION]: '90deg 0deg 0deg',
        [CalState.WAITING_FOR_NOSEDOWN_POSITION]: '0deg 90deg 0deg',
        [CalState.WAITING_FOR_NOSEUP_POSITION]: '0deg -90deg 0deg',
        [CalState.WAITING_FOR_BACK_POSITION]: '0deg 180deg 0deg',
      }
      return AccelStateText[Number(this.state)] ?? '0deg 0deg 0deg'
    },
    current_state_type() {
      if (this.state === CalState.SUCCESS) {
        return 'success'
      }
      if (this.state === CalState.FAIL) {
        return 'error'
      }
      return 'info'
    },
  },
  methods: {
    nextStep() {
      // param needs to match the current step
      const param = [
        CalState.WAITING_FOR_LEVEL_POSITION,
        CalState.WAITING_FOR_LEFT_POSITION,
        CalState.WAITING_FOR_RIGHT_POSITION,
        CalState.WAITING_FOR_NOSEDOWN_POSITION,
        CalState.WAITING_FOR_NOSEUP_POSITION,
        CalState.WAITING_FOR_BACK_POSITION,
      ].indexOf(this.state) + 1

      mavlink2rest.sendMessage({
        header: {
          system_id: 255,
          component_id: 1,
          sequence: 1,
        },
        message: {
          type: 'COMMAND_LONG',
          param1: param,
          param2: 0,
          param3: 0,
          param4: 0,
          param5: 0,
          param6: 0,
          param7: 0,
          command: {
            type: MavCmd.MAV_CMD_ACCELCAL_VEHICLE_POS,
          },
          target_system: autopilot_data.system_id,
          target_component: 1,
          confirmation: 1,
        },
      })
    },
    cleanup() {
      this.dialog = false
      // delay resetting the state to wait for the close animation to finish
      setTimeout(() => { this.state = CalState.IDLE }, 500)
    },
    async startCalibration() {
      const ack_listener = mavlink2rest.startListening('COMMAND_LONG').setCallback((message) => {
        if (message.message.command.type === 'MAV_CMD_ACCELCAL_VEHICLE_POS') {
          switch (message.message.param1) {
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_LEVEL:
              this.state = CalState.WAITING_FOR_LEVEL_POSITION
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_LEFT:
              this.state = CalState.WAITING_FOR_LEFT_POSITION
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_RIGHT:
              this.state = CalState.WAITING_FOR_RIGHT_POSITION
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_NOSEDOWN:
              this.state = CalState.WAITING_FOR_NOSEDOWN_POSITION
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_NOSEUP:
              this.state = CalState.WAITING_FOR_NOSEUP_POSITION
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_BACK:
              this.state = CalState.WAITING_FOR_BACK_POSITION
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_SUCCESS:
              this.state = CalState.SUCCESS
              this.cleanup()
              ack_listener.discard()
              break
            case AccelcalVehiclePos.ACCELCAL_VEHICLE_POS_FAILED:
              this.state = CalState.FAIL
              ack_listener.discard()
              break
            default:
              console.error('Unknown vehicle position:', message.message.param1)
              break
          }
        }
      })
      for await (const value of calibrator.calibrate(PreflightCalibration.ACCELEROMETER)) {
        console.log(value)
      }
      this.state = CalState.WAITING_FOR_VEHICLE_RESPONSE
    },
  },
}
</script>
