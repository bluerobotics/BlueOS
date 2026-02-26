<template>
  <div class="d-flex align-center">
    <v-row>
      <v-col cols="6">
        <span class="text-h6">Increment</span>
      </v-col>
      <v-col cols="6">
        <inline-parameter-editor
          :label="actuator_inc_param?.name"
          :param="actuator_inc_param"
        />
      </v-col>
      <v-row>
        <v-col cols="12">
          <v-alert
            v-if="!has_joystick_function_configured"
            type="warning"
          >
            <span>Joystick functions not configured for this actuator.<br />
              Please configure a joystick button for this actuator using your GCS of choice.</span>
          </v-alert>
        </v-col>
      </v-row>
      <servo-function-range-editor
        :param="param"
      />
    </v-row>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'ServoFunctionActuatorEditor',
  props: {
    param: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  computed: {
    actuator_number(): number | undefined {
      const option_name = this.param.options?.[this.param.value] as string
      const actuator_number = option_name?.match(/\d+/)?.[0]
      if (!actuator_number) return undefined
      return parseInt(actuator_number, 10)
    },
    actuator_inc_param(): Parameter | undefined {
      return autopilot.parameter(`ACTUATOR${this.actuator_number}_INC`)
    },
    btn_params(): Parameter[] {
      // returns all JS button parameters
      return autopilot.parameterRegex('BTN(\\d+)_(S?)FUNCTION') as Parameter[]
    },
    options(): Record<string, string> {
      return this.btn_params[0]?.options as Record<string, string>
    },
    this_actuator_functions(): number[] {
      // returns the joystick button functions for the current actuator
      return Object.entries(this.options)
        .filter(([_, value]) => value.startsWith(`actuator_${this.actuator_number}_`))
        .map(([key]) => parseInt(key, 10))
    },
    has_joystick_function_configured(): boolean {
      return this.btn_params.some((param) => this.this_actuator_functions.includes(param.value as number))
    },
  },
})
</script>
