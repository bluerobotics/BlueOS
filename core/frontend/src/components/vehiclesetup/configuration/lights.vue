<template>
  <div class="main-container">
    <v-card>
      <v-card-title> Lights 1 (RCIN9) </v-card-title>
      <v-card-text>
        The output pin for the primary set of lights:
        <v-select
          v-model="lights1_new_param"
          :items="servo_params"
          :item-text="friendlyName"
          :item-value="'name'"
          label="Lights 1"
        />
      </v-card-text>
    </v-card>
    <v-card>
      <v-card-title> Lights 2 (RCIN10) </v-card-title>
      <v-card-text>
        The output pin for the secondary set of lights:
        <v-select
          v-model="lights2_new_param"
          :items="servo_params"
          :item-text="friendlyName"
          :item-value="'name'"
          label="Lights 2"
        />
      </v-card-text>
    </v-card>
    <v-card>
      <v-card-title> Joystick steps </v-card-title>
      <v-card-text>
        Number of button presses to step from 0% to 100% brightness:
        <br>
        {{ light_steps?.value }} steps result in a {{ (100 / light_steps?.value).toFixed(1) }}%
        increase per button press.
        <v-text-field
          ref="steps_input"
          v-model="steps_new_value"
          label="Joystick steps"
          type="number"
          @input="setSteps"
        />
      </v-card-text>
    </v-card>
  </div>
</template>

<script lang="ts">
import mavlink2rest from '@/libs/MAVLink2Rest'
import ardupilot_capabilities from '@/store/ardupilot_capabilities'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'
import { SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'

enum Lights {
  Lights1 = 59, // RCIN9
  Lights2 = 60, // RCIN10
  DISABLED = 0,
}

export default {
  name: 'LightsConfigration',
  data() {
    return {
      lights1_new_param: undefined as (string | undefined), // item-value must be a primitive
      lights2_new_param: undefined as (string | undefined),
      steps_new_value: 10,
    }
  },
  computed: {
    supports_light_functions(): boolean {
      return ardupilot_capabilities.firmware_supports_light_functions
    },
    light_steps(): Parameter | undefined {
      return autopilot_data.parameter('JS_LIGHTS_STEPS')
    },
    servo_params(): Parameter[] {
      return autopilot_data.parameterRegex('SERVO[0-9]+_FUNCTION')
    },
    lights1_param(): Parameter | undefined {
      return this.servo_params.filter((param) => param.value === Lights.Lights1)[0]
    },
    lights2_param(): Parameter | undefined {
      return this.servo_params.filter((param) => param.value === Lights.Lights2)[0]
    },
    new_lights1_value(): SERVO_FUNCTION {
      return this.supports_light_functions ? SERVO_FUNCTION.LIGHTS1 : SERVO_FUNCTION.RCIN9
    },
    new_lights2_value(): SERVO_FUNCTION {
      return this.supports_light_functions ? SERVO_FUNCTION.LIGHTS2 : SERVO_FUNCTION.RCIN10
    },
  },
  watch: {
    steps_param(new_value: Parameter | undefined) {
      this.steps_new_value = new_value?.value ?? 0
    },
    steps_new_value(new_value: number | undefined) {
      if (new_value) {
        if (this.light_steps?.value === new_value) {
          return
        }
        mavlink2rest.setParam('JS_LIGHTS_STEPS', new_value, autopilot_data.system_id)
      }
    },

    lights1_param(new_value: Parameter | undefined) {
      this.lights1_new_param = new_value?.name
    },
    lights2_param(new_value: Parameter | undefined) {
      this.lights2_new_param = new_value?.name
    },
    lights1_new_param(new_param_name: string | undefined) {
      this.setLights(new_param_name, this.new_lights1_value)
    },
    lights2_new_param(new_param_name: string | undefined) {
      this.setLights(new_param_name, this.new_lights2_value)
    },
  },
  mounted() {
    this.lights1_new_param = this.lights1_param?.name
    this.lights2_new_param = this.lights2_param?.name
    this.steps_new_value = this.light_steps?.value ?? 0
  },
  methods: {
    setLights(new_param_name: string | undefined, lights: SERVO_FUNCTION) {
      if (new_param_name) {
        // reset any other parameter using lights1 to undefined
        for (const old_param of this.servo_params) {
          if (old_param.name === new_param_name) {
            continue
          }
          if (old_param.value === lights) {
            // set the old parameter to DISABLED
            mavlink2rest.setParam(old_param.name, Lights.DISABLED, autopilot_data.system_id)
          }
        }
        mavlink2rest.setParam(new_param_name, lights, autopilot_data.system_id)
      }
    },
    friendlyName(param: Parameter): string {
      return `${param.name.replace('SERVO', 'Servo ').replace('_FUNCTION', '')} (${printParam(param)})`
    },
    setSteps() {
      const new_value = Math.min(Math.max(this.steps_new_value, 1), 10)
      this.$nextTick(() => {
        this.steps_new_value = new_value
      })
      mavlink2rest.setParam('JS_LIGHTS_STEPS', new_value, autopilot_data.system_id)
    },
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
