<template>
  <div class="main-container">
    <v-card style="margin: auto">
      <v-card-title>
        Camera Gimbal Configuration
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col>
            <InlineParameterEditor
              v-if="type_param"
              :param="type_param"
              auto-set
              auto-refresh-params
              label="Gimbal Type (None for no stabilization, 'Servo' for stabilized servo mount)"
            />
            <p v-else>
              Camera mount setup is not supported on this Firmware (MNT1_TYPE param not found).
              please update to a newer version.
            </p>
            <v-select
              v-if="is_servo_type"
              v-model="mnt1_pitch_new_param"
              :items="recommended_params"
              :item-text="friendlyName"
              :item-value="'name'"
              label="Mount 1 Pitch Servo"
            />
            <p v-else-if="type_param">
              Mount is disabled. Enable it by setting the 'Gimbal Type' to 'Servo'
            </p>

            <parameter-switch
              v-if="reverse_pitch_servo"
              :parameter="reverse_pitch_servo"
              label="Reverse servo direction"
            />

            <ThemedSVG v-if="mount_enabled" :src="gimbal_img" />
          </v-col>
        </v-row>
        <v-col v-if="pitch_neutral_angle">
          Neutral Pitch angle. This is the angle the camera goes to when you center it.
          <InlineParameterEditor
            class="mt-5"
            :param="pitch_neutral_angle"
            auto-set
            label="Neutral Pitch angle."
          />
          <v-spacer />
        </v-col>
        <v-col v-if="mount_enabled" style="max-width:500px;">
          These are the PWM values at which the pitch servo reaches its physical limits.
          First adjust the min/max PWM values to match the servo's physical limits.
          Then adjust the min/max angle values so they reflect the actual angles the camera reaches.

          <v-row class="mt-4">
            <v-col>
              <InlineParameterEditor
                v-if="pitch_servo_pwm_max_param"
                :param="pitch_servo_pwm_max_param"
                auto-set
                label="Max PWM"
              />
            </v-col>
            <v-col>
              <InlineParameterEditor
                v-if="pitch_max_param && is_servo_type"
                :param="pitch_max_param"
                auto-set
                label="Max Angle"
              />
            </v-col>
          </v-row>
          <v-row>
            <v-col>
              <InlineParameterEditor
                v-if="pitch_servo_pwm_min_param"
                :param="pitch_servo_pwm_min_param"
                auto-set
                label="Min PWM"
              />
            </v-col>
            <v-col>
              <InlineParameterEditor
                v-if="pitch_min_param && is_servo_type"
                :param="pitch_min_param"
                auto-set
                label="Min Angle"
              />
            </v-col>
          </v-row>
          <v-row>
            <v-alert
              v-tooltip="'How much the PWM value changes per degree. use this to verify against your servo specs.'
                + ' One that reaches +-45º with 1100-1900 PWM, has 8.88us per degree'"
              dense
              text
              colored-border
            >
              PWM/degree: {{ pwm_per_deg.toFixed(2) }} <v-icon>mdi-information</v-icon>
            </v-alert>
          </v-row>
        </v-col>
      </v-card-text>
    </v-card>
  </div>
</template>

<script lang="ts">
import * as gimbal_image from '@/assets/img/configuration/camera/gimbal-pitch.svg'
import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'

export default {
  name: 'CameraConfigration',
  data() {
    return {
      mnt1_pitch_new_param: undefined as (Parameter | undefined),
    }
  },
  computed: {
    recommended_params(): Parameter[] {
      // return parameters in servo_params that are on channel 9 and higher
      return this.servo_params.filter((param) => {
        const servoNumber = parseInt(param.name.replace('SERVO', '').split('_')[0], 10)
        return servoNumber >= 9
      })
    },
    type_param(): Parameter | undefined {
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_TYPE')
    },
    mount_enabled(): boolean {
      return this.is_servo_type
    },
    is_servo_type(): boolean {
      return this.type_param?.value === 1
    },
    pitch_max_param(): Parameter | undefined {
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_PITCH_MAX')
    },
    pitch_min_param(): Parameter | undefined {
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_PITCH_MIN')
    },
    pitch_neutral_angle(): Parameter | undefined {
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_NEUTRAL_Y')
    },
    servo_params(): Parameter[] {
      return autopilot_data.parameterRegex('SERVO[0-9]+_FUNCTION')
    },
    desired_function(): number {
      const tilt_function = 7
      const rcin8_function = 58
      return this.type_param?.value === 1 ? tilt_function : rcin8_function
    },
    current_pitch_servo(): Parameter | undefined {
      return this.servo_params.find((p) => p.value === this.desired_function)
    },
    reverse_pitch_servo(): Parameter | undefined {
      return autopilot_data.parameter(this.current_pitch_servo?.name.replace('FUNCTION', 'REVERSED') ?? '')
    },
    pitch_servo_pwm_max_param(): Parameter | undefined {
      const servo_number = this.current_pitch_servo?.name.match(/SERVO(\d+)_/)?.[1]
      return autopilot_data.parameters.find((p) => p.name === `SERVO${servo_number}_MAX`)
    },
    pitch_servo_pwm_min_param(): Parameter | undefined {
      const servo_number = this.current_pitch_servo?.name.match(/SERVO(\d+)_/)?.[1]
      return autopilot_data.parameters.find((p) => p.name === `SERVO${servo_number}_MIN`)
    },
    gimbal_img(): string {
      return gimbal_image.default
    },
    pwm_per_deg(): number {
      if (this.pitch_max_param && this.pitch_min_param
      && this.pitch_servo_pwm_max_param && this.pitch_servo_pwm_min_param) {
        const pwm_range = this.pitch_servo_pwm_max_param.value - this.pitch_servo_pwm_min_param.value
        const angle_range = this.pitch_max_param.value - this.pitch_min_param.value
        return pwm_range / angle_range
      }
      return 0
    },
  },
  watch: {
    mnt1_pitch_new_param(new_value: string | undefined) {
      if (new_value) {
        if (this.current_pitch_servo?.name === new_value) {
          return
        }
        mavlink2rest.setParam(new_value, this.desired_function, autopilot_data.system_id)
      }
    },
    current_pitch_servo(new_value: Parameter | undefined) {
      if (new_value !== this.mnt1_pitch_new_param) {
        this.mnt1_pitch_new_param = new_value
      }
    },

  },
  mounted() {
    this.mnt1_pitch_new_param = this.current_pitch_servo
  },
  methods: {
    friendlyName(param: Parameter): string {
      return `${param.name.replace('SERVO', 'Servo ').replace('_FUNCTION', '')} (${printParam(param)})`
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

<style>
text {
  font-size: 12px;
  fill: var(--) !important;
  stroke: black;
  stroke-width: 0.5;
}
</style>
