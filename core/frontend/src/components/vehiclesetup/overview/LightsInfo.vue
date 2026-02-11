<template>
  <v-card class="pa-2">
    <v-card-title class="align-center">
      Lights
    </v-card-title>
    <v-card-text>
      <span
        v-for="light in lights"
        :key="light"
        class="d-block"
      >
        <v-icon>
          mdi-dots-horizontal
        </v-icon>
        {{ toBoardFriendlyChannel(light) }}

      </span>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'

import toBoardFriendlyChannel from './common'

export default Vue.extend({
  name: 'LightsInfo',
  computed: {
    boardType() {
      return autopilot.current_board?.name
    },
    lights() {
      const servo_params = autopilot_data.parameterRegex('SERVO.*_FUNCTION')
      const light_params = servo_params.filter(
        (parameter) => parameter.value === SERVO_FUNCTION.RCIN9 || parameter.value === SERVO_FUNCTION.RCIN10,
      )
      return light_params.map((parameter) => parameter.name)
    },
  },
  methods: {
    toBoardFriendlyChannel(servo: string) {
      return toBoardFriendlyChannel(this.boardType, servo)
    },
  },
})
</script>
