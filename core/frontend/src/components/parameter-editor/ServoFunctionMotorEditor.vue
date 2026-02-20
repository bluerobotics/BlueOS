<template>
  <div>
    <v-row class="mb-4">
      <v-col cols="6">
        <span class="text-h6">PWM Type</span>
      </v-col>
      <v-col cols="6">
        <inline-parameter-editor
          :auto-set="true"
          :label="mot_pwm_type_param?.name"
          :param="mot_pwm_type_param"
        />
      </v-col>
    </v-row>
    <v-row class="mb-4">
      <v-col cols="6">
        <span class="text-h6">Reverse Direction</span>
      </v-col>
      <v-col cols="6">
        <inline-parameter-editor
          :auto-set="true"
          :label="reverse_direction_param?.name"
          :param="reverse_direction_param"
        />
      </v-col>
    </v-row>

    <servo-function-range-editor
      v-if="mot_pwm_type_is_supported"
      :param="param"
      :min-param="min_param"
      :trim-param="trim_param"
      :max-param="max_param"
      :title="shared_min_max_param ? 'Shared Motor Configuration' : 'Motor Configuration'"
      :tooltip="tooltip"
    />
    <v-alert
      v-else
      type="warning"
      class="mb-4"
    >
      PWM type is not supported by BlueOS.
    </v-alert>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'
import ServoFunctionRangeEditor from './ServoFunctionRangeEditor.vue'

enum PwmTypes {
  Normal = 0,
  OneShot = 1,
  OneShot125 = 2,
  Brushed = 3,
  DShot150 = 4,
  DShot300 = 5,
  DShot600 = 6,
  DShot1200 = 7,
  PWMRange = 8,
  PWMAngle = 9,
}

export default Vue.extend({
  name: 'ServoFunctionMotorEditor',
  components: {
    InlineParameterEditor,
    ServoFunctionRangeEditor,
  },
  props: {
    param: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  computed: {
    tooltip(): string {
      return this.shared_min_max_param
        ? 'Adjust the minimum, and maximum PWM values for all motors'
        : 'Adjust the minimum, trim, and maximum PWM values for this motor'
    },
    motor_number(): number | undefined {
      const function_name = this.param.options?.[this.param.value] as string
      const motor_number = function_name.match(/\d+/)?.[0]
      if (!motor_number) return undefined
      return parseInt(motor_number, 10)
    },
    shared_min_max_param(): boolean {
      return this.mot_pwm_type === PwmTypes.Normal
    },
    trim_param(): Parameter | undefined {
      if (this.mot_pwm_type === PwmTypes.PWMAngle) {
        return autopilot.parameter(`MOT_${this.motor_number}_TRIM`)
      }
      return undefined
    },
    max_param(): Parameter | undefined {
      if (this.mot_pwm_type === PwmTypes.PWMAngle) {
        return this.getParamByType('_MAX')
      }
      return autopilot.parameter('MOT_PWM_MAX')
    },
    min_param(): Parameter | undefined {
      if (this.mot_pwm_type === PwmTypes.PWMAngle) {
        return this.getParamByType('_MIN')
      }
      return autopilot.parameter('MOT_PWM_MIN')
    },
    mot_pwm_type_param(): Parameter | undefined {
      return autopilot.parameter('MOT_PWM_TYPE')
    },
    mot_pwm_type(): PwmTypes {
      const value = this.mot_pwm_type_param?.value as unknown as PwmTypes
      return value ?? PwmTypes.Normal
    },
    mot_pwm_type_is_supported(): boolean {
      return this.mot_pwm_type === PwmTypes.Normal || this.mot_pwm_type === PwmTypes.PWMAngle
    },
    reverse_direction_param(): Parameter | undefined {
      if (this.mot_pwm_type === PwmTypes.PWMAngle) {
        return this.getParamByType('_REVERSED')
      }
      if (this.mot_pwm_type === PwmTypes.Normal) {
        return autopilot.parameter(`MOT_${this.motor_number}_DIRECTION`)
      }
      return undefined
    },
  },
  methods: {
    getParamByType(type: string): Parameter | undefined {
      if (!this.param?.name) return undefined
      const name = this.param.name.replace('_FUNCTION', type)
      return autopilot.parameter(name)
    },
  },
})
</script>
