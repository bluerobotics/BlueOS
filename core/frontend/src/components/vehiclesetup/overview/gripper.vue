<template>
  <v-card class="pa-2">
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
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { BTN_FUNCTION } from '@/types/autopilot/parameter-sub-enums'

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
      const channel1 = [BTN_FUNCTION.SERVO_1_MIN_MOMENTARY, BTN_FUNCTION.SERVO_1_MAX_MOMENTARY]
      const channel2 = [BTN_FUNCTION.SERVO_2_MIN_MOMENTARY, BTN_FUNCTION.SERVO_2_MAX_MOMENTARY]
      const channel3 = [BTN_FUNCTION.SERVO_3_MIN_MOMENTARY, BTN_FUNCTION.SERVO_3_MAX_MOMENTARY]
      for (const param of btn_params) {
        if (channel1.includes(param.value)) {
          return 9
        }
        if (channel2.includes(param.value)) {
          return 10
        }
        if (channel3.includes(param.value)) {
          return 11
        }
      }
      return null
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
