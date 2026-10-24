<template>
  <v-card class="pa-2">
    <v-card-title class="align-center">
      <v-icon left>
        mdi-hand-back-right
      </v-icon>
      Gripper
    </v-card-title>
    <v-card-text v-if="gripper === null">
      Not configured
    </v-card-text>

    <v-card-text v-else-if="gripper === 'MAVLink'">
      MAVLink
    </v-card-text>

    <v-card-text v-else-if="!supports_actuators">
      {{ toBoardFriendlyChannel(`SERVO${gripper + LEGACY_OUTPUT_OFFSET}_FUNCTION`) }}
    </v-card-text>

    <v-card-text v-else-if="gripper_outputs.length === 0" class="error--text">
      Gripper is on Actuator {{ gripper }}, but no output is set to Actuator {{ gripper }}
    </v-card-text>

    <v-card-text v-else>
      Actuator {{ gripper }}: {{ gripper_outputs.map((output) => toBoardFriendlyChannel(output)).join(', ') }}
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { BTN_FUNCTION, SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'

import toBoardFriendlyChannel from './common'

const ACTUATOR_COUNT = 6
const GRIPPER_ACTIONS = ['MIN', 'MAX', 'MIN_MOMENTARY', 'MAX_MOMENTARY', 'MIN_TOGGLE', 'MAX_TOGGLE']
// Older ArduSub hardcoded the servo_1..3 button functions to outputs 9..11
const LEGACY_OUTPUT_OFFSET = 8

export default Vue.extend({
  name: 'GripperInfo',
  data() {
    return {
      LEGACY_OUTPUT_OFFSET,
    }
  },
  computed: {
    gripper(): 'MAVLink' | number | null {
      const mavlink = autopilot_data.parameter('GRIP_ENABLE')?.value === 1
      if (mavlink) {
        return 'MAVLink'
      }

      const btn_params = autopilot_data.parameterRegex('^BTN(\\d+)_S?FUNCTION$')

      // we cannot directly detect a gripper, so we search for an actuator with the min/max actions
      // instead
      for (const param of btn_params) {
        for (let actuator = 1; actuator <= ACTUATOR_COUNT; actuator += 1) {
          const functions = GRIPPER_ACTIONS.map(
            (action) => BTN_FUNCTION[`SERVO_${actuator}_${action}` as keyof typeof BTN_FUNCTION],
          )
          if (functions.includes(param.value)) {
            return actuator
          }
        }
      }
      return null
    },
    supports_actuators(): boolean {
      return autopilot_data.firmware_supports_actuators
    },
    gripper_outputs(): string[] {
      if (typeof this.gripper !== 'number') {
        return []
      }
      const actuator_function = SERVO_FUNCTION.ACTUATOR1 + this.gripper - 1
      return autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
        .filter((param) => param.value === actuator_function)
        .map((param) => param.name)
    },
    boardType() {
      return autopilot.current_board?.name
    },
  },
  methods: {
    toBoardFriendlyChannel(servo: string): string {
      return toBoardFriendlyChannel(this.boardType, servo)
    },
  },
})
</script>
