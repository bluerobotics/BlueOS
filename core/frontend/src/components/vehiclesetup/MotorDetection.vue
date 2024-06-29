<template>
  <v-dialog
    v-if="is_sub"
    v-model="dialog"
    max-width="1000px"
    :persistent="status == statuses.RUNNING"
    @input="status = statuses.IDLE"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        dark
        v-bind="attrs"
        v-on="on"
      >
        Detect Reversed Motors
      </v-btn>
    </template>

    <v-card class="pa-5" style="overflow-x: hidden;">
      <v-card-title class="text-h5 justify-center">
        Automatic Motor Reversal Detection
      </v-card-title>
      <v-sheet v-if="display_status" class="elevation-1 pa-3 ma-8">
        <StatusTextWatcher :filter="/thrust|Thrust|Motor|MOTOR/" @message="updateStatus" />
      </v-sheet>
      <v-row v-if="status == statuses.IDLE">
        <v-col rows="3" class="justify-center">
          <ThemedSVG src="/img/icons/motordetection.svg" />
        </v-col>
        <v-col cols="8">
          <v-card-text>
            <p class="text-justify">
              Tests whether any of the motors are wired to spin backwards,
              and automatically reverses their control signals as relevant.
            </p>
            <p class="text-justify">
              The test relies on the <b>motors being correctly connected</b>
              according to the selected vehicle frame, and spins each motor
              individually to check whether it generates thrust in the expected direction.
              The vehicle should be in calm water and far from walls and objects.
            </p>
          </v-card-text>
        </v-col>
      </v-row>

      <v-sheet v-if="[statuses.RUNNING].includes(status)" class=" pa-3 ma-8">
        <v-progress-linear indeterminate />
        The test is running. The vehicle will move slightly as each motor is tested.
      </v-sheet>

      <v-alert
        v-if="status == statuses.COMPLETE"
        class="ma-8"
        dense
        text
        type="success"
      >
        Motor direction detection is complete. The vehicle is ready for normal operation.
      </v-alert>
      <v-alert
        v-if="status == statuses.FAILED"
        class="ma-8"
        type="error"
        dense
        text
      >
        Motor direction detection failed. Please check the troubleshooting section below.
      </v-alert>
      <v-card-text v-if="status == statuses.FAILED" class="ma-4">
        <p>
          Motor testing can fail due to any unexpected motions of the vehicle.
          Here are some common failure causes, and potential solutions:
        </p>
        <v-sheet class="elevation-2 pa-1 mt-3 mb-3 mr-9 rounded-lg">
          <v-simple-table class="ma-0">
            <thead>
              <tr>
                <th>Cause</th>
                <th>Solutions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>no movement</td>
                <td>
                  - ensure the vehicle is in the water<br>
                  - ensure the ESC is powered and receiving valid signals<br>
                  - ensure the thruster is connected to the ESC
                </td>
              </tr>
              <tr>
                <td>external movement</td>
                <td>
                  - ensure the vehicle is in calm water
                  - ensure the vehicle is not colliding with other objects
                </td>
              </tr>
              <tr>
                <td>poor movement estimation</td>
                <td>
                  - ensure the sensors are well calibrated<br>
                  - ensure that no external forces are moving the vehicle during the test
                </td>
              </tr>
              <tr>
                <td>incorrect frame selection</td>
                <td>
                  - choose the frame that matches your vehicle (or make a custom one)<br>
                  - ensure the frame's motion contribution factors suit the positions and orientations of your
                  thrusters relative to the vehicle's centers of mass and volume (you may need to trim with
                  ballast and/or buoyancy)
                </td>
              </tr>
              <tr>
                <td>incorrect motor mapping</td>
                <td>
                  - ensure the thrusters are connected to the correct output channels of the flight controller,
                  and in the correct order to match the frame numbering
                  - load the recommended parameters for your frame
                </td>
              </tr>
            </tbody>
          </v-simple-table>
        </v-sheet>
        <p>
          If necessary it is possible to manually test and set the motor spin directions instead.
        </p>
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn
          v-if="status == statuses.IDLE"
          color="primary"
          dark
          :disabled="running"
          @click="start"
        >
          Start Detection
        </v-btn>
        <v-btn
          v-if="status === statuses.FAILED"
          color="primary"
          dark
          :disabled="running"
          @click="status = statuses.IDLE"
        >
          retry
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import { ArduSubMode } from '@/libs/firmware/ardupilot/ardusub'
import autopilot from '@/store/autopilot_manager'
import { FirmwareVehicleType } from '@/types/autopilot'
import {
  armDisarm, getMode, isArmed, setMode,
} from '@/utils/ardupilot_mavlink'

import StatusTextWatcher from '../common/StatusTextWatcher.vue'

enum status {
  IDLE,
  STARTING,
  RUNNING,
  COMPLETE,
  FAILED,
}

export default Vue.extend({
  name: 'MotorDetection',
  components: {
    ThemedSVG: () => import('@/components/utils/themedSVG.vue'),
    StatusTextWatcher,
  },
  data: () => ({
    dialog: false,
    status: status.IDLE,
    timeout_timer: undefined as undefined | number,
  }),
  computed: {
    display_status(): boolean {
      return [status.STARTING, status.RUNNING, status.FAILED].includes(this.status)
    },
    is_sub(): boolean {
      return autopilot.firmware_vehicle_type === FirmwareVehicleType.ArduSub
    },
    running(): boolean {
      return this.is_sub && getMode() === ArduSubMode.MOTOR_DETECT && isArmed()
    },
    statuses(): typeof status {
      return status
    },
  },
  watch: {
    running(new_state: boolean) {
      if (new_state) {
        this.status = status.RUNNING
      }
    },
  },
  methods: {
    async start() {
      // TODO: use the enum from mavlink2rest-ts when it gets fixed
      this.status = status.STARTING
      setMode(ArduSubMode.MOTOR_DETECT).then(() => {
        armDisarm(true, true)
        // this timer gets cleared and bumped on every message we receive
        this.timeout_timer = setTimeout(() => {
          this.status = status.FAILED
        }, 5000)
      })
    },
    async updateStatus(message: string) {
      clearInterval(this.timeout_timer)
      if (message.includes('complete')) {
        // TODO: use the enum from mavlink2rest-ts when it gets fixed
        await setMode(ArduSubMode.MANUAL)
        this.status = status.COMPLETE
      } else if (message.includes('Failed!')) {
        this.status = status.FAILED
        await setMode(ArduSubMode.MANUAL)
      } else {
        this.timeout_timer = setTimeout(() => {
          this.status = status.FAILED
        }, 5000)
      }
    },
  },
})
</script>
