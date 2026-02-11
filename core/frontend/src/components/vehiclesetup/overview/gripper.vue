<template>
  <v-card class="ma-2 pa-2" max-width="250px">
    <v-card-title class="align-center">
      Gripper
    </v-card-title>
    <v-card-text v-if="gripper === null">
      Not configured
    </v-card-text>

    <v-card-text v-else-if="gripper === 'MAVLink'">
      MAVLink
    </v-card-text>

    <v-card-text v-else>
      {{ toBoardFriendlyChannel(`SERVO${gripper}_FUNCTION`) }}
    </v-card-text>
    <v-card-text v-if="misconfigured_gripper" class="red--text">
      {{ misconfigured_gripper }}
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import ardupilot_capabilities from '@/store/ardupilot_capabilities'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { BTN_FUNCTION, SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'

import toBoardFriendlyChannel from './common'

export default Vue.extend({
  name: 'GripperInfo',
  computed: {
    gripper() {
      const mavlink = autopilot_data.parameter('GRIP_ENABLE')?.value === 1
      if (mavlink) {
        return 'MAVLink'
      }

      const btn_params = autopilot_data.parameterRegex('^BTN(\\d+)_S?FUNCTION$')

      // we cannot directly detect a gripper, so we search for a channel with the min/max momentary actions
      // instead
      const channel1 = [
        BTN_FUNCTION.SERVO_1_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_1_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_1_MIN_TOGGLE,
        BTN_FUNCTION.SERVO_1_MAX_TOGGLE,
        BTN_FUNCTION.SERVO_1_MIN,
        BTN_FUNCTION.SERVO_1_MAX,
      ]
      const channel2 = [
        BTN_FUNCTION.SERVO_2_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_2_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_2_MIN_TOGGLE,
        BTN_FUNCTION.SERVO_2_MAX_TOGGLE,
        BTN_FUNCTION.SERVO_2_MIN,
        BTN_FUNCTION.SERVO_2_MAX,
      ]
      const channel3 = [
        BTN_FUNCTION.SERVO_3_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_3_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_3_MIN_TOGGLE,
        BTN_FUNCTION.SERVO_3_MAX_TOGGLE,
        BTN_FUNCTION.SERVO_3_MIN,
        BTN_FUNCTION.SERVO_3_MAX,
      ]
      const channel4 = [
        BTN_FUNCTION.SERVO_4_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_4_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_4_MIN_TOGGLE,
        BTN_FUNCTION.SERVO_4_MAX_TOGGLE,
        BTN_FUNCTION.SERVO_4_MIN,
        BTN_FUNCTION.SERVO_4_MAX,
      ]
      const channel5 = [
        BTN_FUNCTION.SERVO_5_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_5_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_5_MIN_TOGGLE,
        BTN_FUNCTION.SERVO_5_MAX_TOGGLE,
        BTN_FUNCTION.SERVO_5_MIN,
        BTN_FUNCTION.SERVO_5_MAX,
      ]
      const channels = [channel1, channel2, channel3, channel4, channel5]
      for (const param of btn_params) {
        for (const [index, channel] of channels.entries()) {
          if (channel.includes(param.value)) {
            return index + 1
          }
        }
      }
      return null
    },
    boardType() {
      return autopilot.current_board?.name
    },
    configured_actuators(): number[] {
      const actuator_functions = [
        SERVO_FUNCTION.ACTUATOR1,
        SERVO_FUNCTION.ACTUATOR2,
        SERVO_FUNCTION.ACTUATOR3,
        SERVO_FUNCTION.ACTUATOR4,
        SERVO_FUNCTION.ACTUATOR5,
        SERVO_FUNCTION.ACTUATOR6,
      ]
      return autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
        .filter((param) => actuator_functions.includes(param.value))
        .map((param) => actuator_functions.indexOf(param.value) + 1)
    },

    misconfigured_gripper(): string | null {
      if (this.gripper === 'MAVLink') {
        return null
      }
      if (!ardupilot_capabilities.firmware_supports_actuators) {
        if (this.gripper === null) {
          return 'No gripper configured.'
        }
        return null
      }
      if (this.gripper === null) {
        return 'No gripper configured.'
      }
      if (this.configured_actuators.includes(this.gripper)) {
        if (!this.configured_actuators.includes(this.gripper + 1)) {
          return `Gripper is configured on Actuator ${this.gripper},`
            + ` but no Output PWM is configured for Actuator ${this.gripper + 1}.`
        }
        return null
      }
      return null
    },
  },
  methods: {
    toBoardFriendlyChannel(servo: string): string {
      return toBoardFriendlyChannel(this.boardType, servo)
    },
  },
})
</script>
