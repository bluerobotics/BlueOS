<template>
  <v-card class="ma-2 pa-2">
    <v-card-title class="align-center">
      Leak
    </v-card-title>
    <v-card-text>
      <div
        v-for="leak in leaks"
        :key="leak.order"
        class="d-block mb-1"
      >
        <b>Leak sensor {{ leak.order }}: </b>
        <template v-if="leak.pin?.value !== -1">
          <span class="ml-3 d-block"><b>Pin:</b> {{ printParam(leak.pin) }}</span>
          <span class="ml-3 d-block"><b>Logic:</b> {{ printParam(leak.logic) }}</span>
        </template>
        <template v-else>
          Disabled
        </template>
      </div>
      <b>Failsafe:</b> {{ printParam(failsafe) }}
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'LeakInfo',
  computed: {
    leak_params(): Parameter[] {
      return autopilot_data.parameterRegex('.*LEAK.*')
    },
    failsafe(): Parameter | undefined {
      return autopilot_data.parameter('FS_LEAK_ENABLE')
    },
    leaks(): {order: number, pin?: Parameter, logic?: Parameter}[] {
      const leaks = []
      const size = autopilot_data.parameterRegex('^LEAK(\\d+)_PIN$').length
      for (let i = 1; i <= size; i += 1) {
        leaks.push({
          order: i,
          pin: this.leak_params.find((params) => params.name.endsWith(`${i}_PIN`)),
          logic: this.leak_params.find((params) => params.name.endsWith(`${i}_LOGIC`)),
        })
      }
      return leaks
    },

  },
  methods: {
    printParam,
  },
})
</script>
