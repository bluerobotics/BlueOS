<template>
  <div class="pt-1 pb-1">
    <div v-for="(parameters, section) in filtered_params">
      <v-sheet class="ma-5">
        <v-card-title>{{ section }}</v-card-title>
        <div class="d-flex d-col flex-wrap">
          <v-card v-for="param in parameters" elevation="2" class="ma-2 d-flex flex-column" min-width="200px" max-width="250px">
            <v-card-title> {{ param.name }}</v-card-title>
            <v-card-text>
              {{ param.description }}
            </v-card-text>
            <div class="flex-grow-1" />
            <v-card-actions>
              <v-text-field
                label="Current value"
                :value="`${printParam(param)} ${param.units ?? ''}`"

                disabled
              />
              <v-btn small>
                <v-icon>mdi-pencil</v-icon>
              </v-btn>
            </v-card-actions>
          </v-card>
        </div>
      </v-sheet>
    </div>
  </div>
</template>

<script lang="ts">
import { Dictionary } from 'vue-router/types/router.js'

import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'

enum Lights {
  Lights1 = 59, // RCIN9
  Lights2 = 60, // RCIN10
  DISABLED = 0,
}

const FS_PARAMS = {
  Communication:
  [
    'FS_PILOT_INPUT',
    'FS_PILOT_TIMEOUT',
    'FS_GCS_ENABLE',
  ],
  Sensors:
  [
    'FS_LEAK_ENABLE',
    'FS_PRESS_ENABLE',
    'FS_TEMP_ENABLE',
    'FS_PRESS_MAX',
    'FS_TEMP_MAX',
    'FS_EKF_ACTION',
  ],
  Battery:
  [
    'BATT_FS_VOLTSRC',
    'BATT_FS_LOW_ACT',
    'BATT_FS_CRT_ACT',
  ],
}

export default {
  name: 'FailsafesConfigration',
  computed: {
    filtered_params(): Dictionary<(Parameter | undefined)[]> {
      // return parameters in servo_params that are on channel 9 and higher
      const params = {} as Dictionary<(Parameter | undefined)[]>
      for (const [section, parameters] of Object.entries(FS_PARAMS)) {
        params[section] = parameters.map((param) => autopilot_data.parameter(param))
      }
      return params
    },
  },
  methods: {
    printParam,
  },
}
</script>
<style scoped>
.main-container {
  display: flex;
  column-gap: 10px;
  padding: 10px;
}
</style>
