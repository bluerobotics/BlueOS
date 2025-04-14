<template>
  <div class="main-container">
    <v-card style="margin: auto">
      <v-card-title>
        Camera Gimbal Configuration
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col>
            <p v-if="!type_param">
              Camera mount setup is not supported on this firmware (MNT1_TYPE param not found).
              Please update to a newer autopilot firmware version.
            </p>
            <v-select
              v-if="is_servo_type"
              v-model="mnt1_pitch_new_param"
              :items="servo_params"
              :item-text="friendlyName"
              :item-value="'name'"
              label="Mount 1 Pitch Servo"
            />
            <p v-else-if="type_param">
              Mount is disabled. Enable it by setting the 'Gimbal Type' to 'Servo'.
            </p>

            <v-row>
              <v-col>
                <parameter-switch
                  v-if="reverse_pitch_servo"
                  :parameter="reverse_pitch_servo"
                  label="Reverse servo direction"
                />
              </v-col>
              <v-col>
                <v-switch
                  v-if="is_servo_type"
                  v-model="is_stabilized"
                  label="Stabilize mount"
                />
              </v-col>
            </v-row>

            <ThemedSVG v-if="mount_enabled" :src="gimbal_img" />
          </v-col>
        </v-row>
        <v-col v-if="mount_enabled" style="max-width:650px;">
          <v-row>
            <v-card>
              <v-card-title>
                Step 1: Find the physical limits
              </v-card-title>
              <v-card-text>
                <v-row class="ma-3">
                  <p>
                    To find the physical limits of the servo, move the camera to the minimum and maximum positions,
                    then adjust the minimum/maximum PWMs values until it reaches the furthest it can move
                    without hitting other components.
                  </p>
                  <v-row>
                    <v-col>
                      <InlineParameterEditor
                        v-if="pitch_servo_pwm_max_param"
                        style="border-left: 2px solid var(--v-negative-base); padding-left: 10px;"
                        :param="pitch_servo_pwm_max_param"
                        auto-set
                        label="Max PWM"
                        @change="update_max_pwm"
                      />
                    </v-col>
                    <v-col>
                      <InlineParameterEditor
                        v-if="pitch_servo_pwm_min_param"
                        style="border-left: 2px solid var(--v-water-base); padding-left: 10px;"
                        :param="pitch_servo_pwm_min_param"
                        auto-set
                        label="Min PWM"
                        @change="update_min_pwm"
                      />
                    </v-col>
                  </v-row>
                  <v-alert dense small outlined type="warning" style="margin: auto;">
                    The gimbal will move to the new PWM values as you adjust them.
                  </v-alert>
                </v-row>
              </v-card-text>
            </v-card>
            <v-card>
              <v-card-title>
                Step 2: Measure the actual angles
              </v-card-title>
              <v-card-text>
                <v-row class="ma-3">
                  <p>
                    Measure the rotation limit angles and input them below.
                    This will allow Ardupilot to accurately report the camera rotation angle
                    from its commanded servo PWM value.
                  </p>
                  <v-col>
                    <InlineParameterEditor
                      v-if="pitch_max_param"
                      style="border-left: 2px solid var(--v-negative-base); padding-left: 10px;"
                      :param="pitch_max_param"
                      auto-set
                      label="Max Angle"
                    />
                  </v-col>
                  <v-col>
                    <InlineParameterEditor
                      v-if="pitch_min_param"
                      style="border-left: 2px solid var(--v-water-base); padding-left: 10px;"
                      :param="pitch_min_param"
                      auto-set
                      label="Min Angle"
                    />
                  </v-col>
                </v-row>
                <v-row class="ma-3">
                  <v-col>
                    <strong>Calculated PWM/degree:</strong> {{ pwm_per_deg.toFixed(2) }} <br>
                    <p>
                      This represents how much the PWM value changes per degree. Use this to
                      verify against your servo specs.
                      One that reaches +-45º with 1100-1900 PWM (all current BlueRobotics servos),
                      has a ratio of 8.88µs per degree.
                      This can help you make sure you measured the angles correctly.
                    </p>
                  </v-col>
                </v-row>
              </v-card-text>
            </v-card>
          </v-row>
        </v-col>
      </v-card-text>
    </v-card>
  </div>
</template>

<script lang="ts">
import * as gimbal_image from '@/assets/img/configuration/camera/gimbal-pitch.svg'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import Parameter, { printParam } from '@/types/autopilot/parameter'
import { Dictionary } from '@/types/common'
import mavlink_store_get from '@/utils/mavlink'

export default {
  name: 'CameraConfigration',
  data() {
    return {
      mnt1_pitch_new_param: undefined as (Parameter | undefined),
    }
  },
  computed: {
    is_stabilized: {
      get(): boolean {
        return this.type_param?.value === 1
      },
      set(value: boolean): void {
        this.update_stabilized(value)
      },
    },
    max_line(): HTMLElement | null {
      return document.getElementById('path-max')
    },
    min_line(): HTMLElement | null {
      return document.getElementById('path-min')
    },
    camera_path(): HTMLElement | null {
      return document.getElementById('path-camera')
    },
    max_text(): HTMLElement | null {
      return document.getElementById('text-max')
    },
    min_text(): HTMLElement | null {
      return document.getElementById('text-min')
    },
    pwm_text(): HTMLElement | null {
      return document.getElementById('text-pwm')
    },
    angle_text(): HTMLElement | null {
      return document.getElementById('text-angle')
    },

    type_param(): Parameter | undefined {
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_TYPE')
    },
    mount_enabled(): boolean {
      return this.is_servo_type
    },
    is_servo_type(): boolean {
      return this.type_param?.value === 1 || this.type_param?.value === 7
    },
    pitch_max_param(): Parameter | undefined {
      if (this.servo_reversed) {
        return autopilot_data.parameters.find((p) => p.name === 'MNT1_PITCH_MAX')
      }
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_PITCH_MIN')
    },
    pitch_max_value(): number {
      if (this.servo_reversed) {
        return -(this.pitch_max_param?.value ?? 0)
      }
      return this.pitch_max_param?.value ?? 0
    },
    pitch_min_value(): number {
      if (this.servo_reversed) {
        return -(this.pitch_min_param?.value ?? 0)
      }
      return this.pitch_min_param?.value ?? 0
    },
    pitch_min_param(): Parameter | undefined {
      if (this.servo_reversed) {
        return autopilot_data.parameters.find((p) => p.name === 'MNT1_PITCH_MIN')
      }
      return autopilot_data.parameters.find((p) => p.name === 'MNT1_PITCH_MAX')
    },
    servo_params(): Parameter[] {
      return autopilot_data.parameterRegex('SERVO[0-9]+_FUNCTION')
    },
    desired_function(): number {
      const tilt_function = 7
      return tilt_function
    },
    current_pitch_servo(): Parameter | undefined {
      return this.servo_params.find((p) => p.value === this.desired_function)
    },
    current_pitch_servo_index(): number {
      return this.servo_params.findIndex((p) => p.value === this.desired_function)
    },
    reverse_pitch_servo(): Parameter | undefined {
      return autopilot_data.parameter(this.current_pitch_servo?.name.replace('FUNCTION', 'REVERSED') ?? '')
    },
    servo_reversed(): boolean {
      return this.reverse_pitch_servo?.value === 1
    },
    pitch_servo_pwm_max_param(): Parameter | undefined {
      const servo_number = this.current_pitch_servo?.name.match(/SERVO(\d+)_/)?.[1]
      if (this.servo_reversed) {
        return autopilot_data.parameters.find((p) => p.name === `SERVO${servo_number}_MIN`)
      }
      return autopilot_data.parameters.find((p) => p.name === `SERVO${servo_number}_MAX`)
    },
    pitch_servo_pwm_min_param(): Parameter | undefined {
      const servo_number = this.current_pitch_servo?.name.match(/SERVO(\d+)_/)?.[1]
      if (this.servo_reversed) {
        return autopilot_data.parameters.find((p) => p.name === `SERVO${servo_number}_MAX`)
      }
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
    mount_output_pwm(): number {
      const data = mavlink_store_get(mavlink, 'SERVO_OUTPUT_RAW.messageData.message') as Dictionary<number> | undefined
      if (!data) {
        return -1
      }
      return data[`servo${this.current_pitch_servo_index + 1}_raw`]
    },
    mount_output_angle(): number {
      const data = mavlink_store_get(mavlink, 'SERVO_OUTPUT_RAW.messageData.message') as Dictionary<number> | undefined
      if (!data) {
        return -1
      }
      const max_angle = this.pitch_max_param?.value ?? 0
      const min_angle = this.pitch_min_param?.value ?? 0
      const angle_range = Math.abs(max_angle - min_angle)
      const max_pwm = this.pitch_servo_pwm_max_param?.value ?? 0
      const min_pwm = this.pitch_servo_pwm_min_param?.value ?? 0
      const pwm_range = max_pwm - min_pwm
      if (angle_range === 0 || pwm_range === 0) {
        return 0
      }
      if (this.servo_reversed) {
        return -min_angle - (this.mount_output_pwm - min_pwm) * angle_range / pwm_range
      }
      return max_angle - (this.mount_output_pwm - max_pwm) * angle_range / pwm_range
    },

  },
  watch: {
    mnt1_pitch_new_param(new_value: Parameter | undefined) {
      if (!this.current_pitch_servo) {
        return
      }
      if (new_value) {
        if (this.current_pitch_servo?.name === new_value.name) {
          return
        }
        mavlink2rest.setParam(new_value.name, this.desired_function, autopilot_data.system_id)
      }
    },
    current_pitch_servo(new_value: Parameter | undefined) {
      if (new_value !== this.mnt1_pitch_new_param) {
        this.mnt1_pitch_new_param = new_value
      }
    },
    mount_output_angle() {
      this.update_svg()
    },
    pitch_max_value() {
      this.update_svg()
    },
    pitch_min_value() {
      this.update_svg()
    },
  },
  mounted() {
    this.mnt1_pitch_new_param = this.current_pitch_servo
    mavlink.setMessageRefreshRate({ messageName: 'SERVO_OUTPUT_RAW', refreshRate: 2 })
  },
  methods: {
    update_stabilized(new_value: boolean): void {
      mavlink2rest.setParam('MNT1_TYPE', new_value ? 1 : 7, autopilot_data.system_id)
    },
    friendlyName(param: Parameter): string {
      return `${param.name.replace('SERVO', 'Servo ').replace('_FUNCTION', '')} (${printParam(param)})`
    },
    update_max_pwm(): void {
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_GIMBAL_MANAGER_TILTPAN,
        180.0,
      )
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_MOUNT_CONTROL,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        3.0, // MAV_MOUNT_MODE_RC_TARGETING
      )
    },
    update_min_pwm(): void {
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_GIMBAL_MANAGER_TILTPAN,
        -180.0,
      )
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_MOUNT_CONTROL,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        3.0, // MAV_MOUNT_MODE_RC_TARGETING
      )
    },
    update_svg(): void {
      const new_angle = this.mount_output_angle
      const max_angle = this.pitch_max_value
      const min_angle = this.pitch_min_value
      const center_x = 130
      const center_y = 119
      let drawing_angle = 0
      if (this.max_line && this.max_text) {
        drawing_angle = 47.5
        this.max_line.setAttribute('transform', `rotate(${max_angle + drawing_angle}, ${center_x}, ${center_y} )`)
        this.max_text.setAttribute('transform', `rotate(${max_angle + drawing_angle}, ${center_x}, ${center_y} )`)
      }
      if (this.min_line && this.min_text) {
        drawing_angle = -30.5
        this.min_line.setAttribute('transform', `rotate(${min_angle + drawing_angle}, ${center_x}, ${center_y} )`)
        this.min_text.setAttribute('transform', `rotate(${min_angle + drawing_angle}, ${center_x}, ${center_y} )`)
      }
      if (this.pwm_text) {
        this.pwm_text.innerHTML = `PWM: ${this.mount_output_pwm}µs`
      }
      if (this.angle_text) {
        this.angle_text.innerHTML = `Angle: ${this.mount_output_angle.toFixed(2)}º`
      }
      if (this.camera_path) {
        this.camera_path.setAttribute('transform', `rotate(${new_angle}, ${center_x}, ${center_y} )`)
      }
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
