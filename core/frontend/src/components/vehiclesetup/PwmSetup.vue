<template>
  <div>
    <v-row class="mt-5">
      <v-col
        cols="12"
        sm="8"
      >
        <v-card>
          <vehicle-viewer :highlight="highlight" :transparent="true" :autorotate="false" />
        </v-card>
        <v-card class="mt-3">
          <v-overlay :value="!has_focus">
            <div class="text-h4 py-12 px-12">
              Motor test is disabled when the page is out of focus
            </div>
          </v-overlay>
          <v-simple-table
            dense
          >
            <template #default>
              <thead>
                <tr>
                  <th class="text-left subtitle-1 font-weight-bold">
                    Motor Test
                  </th>
                  <th />
                  <th>
                    <div class="flex-row justify-space-between d-flex">
                      <v-switch
                        v-model="desired_armed_state"
                        :loading="desired_armed_state !== (is_armed) ? 'warning' : null"
                        :disabled="!is_manual"
                        class="mx-1 flex-grow-0"
                        :label="arm_disarm_switch_label"
                        :color="`${is_armed ? 'error' : 'success'}`"
                        @change="arm_disarm_switch_change"
                      />
                      <div style="width:50%" class="d-flex justify-center mt-3">
                        <MotorDetection />
                      </div>
                    </div>
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody class="align-center">
                <tr
                  v-for="motor of available_motors"
                  :key="'mot' + motor.servo"
                  width="100%"
                  height="65"
                  class="ma-0 pa-0"
                  @mouseover="highlightMotor(motor)"
                  @mouseleave="highlight = default_highlight"
                >
                  <td width="20%">
                    {{ motor.name }}
                    <span v-if="motor.servo !== motor.motor">
                      (Output {{ motor.servo }})
                    </span>
                  </td>
                  <td width="10%">
                    <parameterSwitch
                      v-if="motor.reverse_parameter"
                      :parameter="motor.reverse_parameter"
                      :on-value="reverse_on_value"
                      :off-value="reverse_off_value"
                      label="Reversed"
                    />
                  </td>
                  <td width="80%">
                    <v-slider
                      v-model="motor_targets[motor.target]"
                      class="align-center"
                      :min="1000"
                      :max="2000"
                      hide-details
                      thumb-label
                      color="primary"
                      track-color="primary"
                      :disabled="!is_armed || !is_manual"
                      @mouseup="restart_motor_zeroer()"
                      @mousedown="pause_motor_zeroer()"
                    />
                    <div
                      class="v-progress-linear"
                      style="height: 25px;"
                    >
                      <div
                        class="pwm-bar-bg"
                      />
                      <div
                        class="pwm-bar"
                        :style="styleForMotorBar(motor_outputs[motor.servo])"
                      />
                      <div class="pwm-bar-content">
                        <strong>{{ (motor_outputs[motor.servo] - 1500) / 10 }}%</strong>
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </template>
          </v-simple-table>
        </v-card>
      </v-col>
      <v-col
        cols="12"
        sm="4"
      >
        <v-card>
          <v-simple-table>
            <template #default>
              <thead>
                <tr>
                  <th class="text-left">
                    Name
                  </th>
                  <th class="text-left">
                    Value
                  </th>
                  <th class="text-left">
                    Output
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(item, index) in servo_function_parameters"
                  :key="item.name"
                  style="cursor: pointer;"
                  @mouseover="highlight = [servoToHighlight(item)]"
                  @mouseleave="highlight = default_highlight"
                  @click="showParamEdit(item)"
                >
                  <td v-tooltip="item.name">
                    {{ convert_servo_name(item.name) }}
                  </td>
                  <td>{{ parameterToUserFriendlyText(item) }}</td>
                  <td>{{ servo_output[index] }}</td>
                </tr>
              </tbody>
            </template>
          </v-simple-table>
        </v-card>
      </v-col>
    </v-row>
    <servo-function-editor-dialog
      v-if="edit_param_dialog"
      v-model="edit_param_dialog"
      :param="selected_param"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import { fetchCurrentBoard } from '@/components/autopilot/AutopilotManagerUpdater'
import ServoFunctionEditorDialog from '@/components/parameter-editor/ServoFunctionEditorDialog.vue'
import MotorDetection from '@/components/vehiclesetup/MotorDetection.vue'
import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'
import {
  MavModeFlag,
} from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import { Message } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-message'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import mavlink from '@/store/mavlink'
import { FirmwareVehicleType } from '@/types/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'
import { SERVO_FUNCTION as ROVER_FUNCTIONS } from '@/types/autopilot/parameter-rover-enums'
import { SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'
import { Dictionary } from '@/types/common'
import { armDisarm, doMotorTest } from '@/utils/ardupilot_mavlink'
import mavlink_store_get from '@/utils/mavlink'

import ParameterSwitch from '../common/ParameterSwitch.vue'

interface MotorTestTarget {
  name: string
  motor: number
  servo: number // target and servo differ in rover
  target: number
  direction: number
  reverse_parameter?: Parameter
}

const rover_function_map = {
  70: 1, // ROVER_FUNCTIONS.THROTTLE
  26: 2, // ROVER_FUNCTIONS.GRODUNDSTEERING
  73: 3, // ROVER_FUNCTIONS.THROTTLELEFT
  74: 4, // ROVER_FUNCTIONS.THROTTLERIGHT
  89: 5, // ROVER_FUNCTIONS.MAINSAIL
} as Dictionary<number>

const param_value_map = {
  Submarine: {
    RCIN9: 'Lights 1',
    RCIN10: 'Lights 2',
    RCIN11: 'Video Switch',
  },
} as Dictionary<Dictionary<string>>

export default Vue.extend({
  name: 'PwmSetup',
  components: {
    ServoFunctionEditorDialog,
    ParameterSwitch,
    VehicleViewer,
    MotorDetection,
  },
  data() {
    return {
      highlight: ['Motor', 'Light', 'Mount', 'Gripper'],
      default_highlight: ['Motor', 'Light', 'Mount', 'Gripper'],
      edit_param_dialog: false,
      selected_param: undefined as Parameter | undefined,
      motor_targets: {} as {[key: number]: number},
      motor_zeroer_interval: undefined as undefined | number,
      motor_writer_interval: undefined as undefined | number,
      desired_armed_state: false,
      has_focus: true,
      motors_zeroed: false,
      // These two change from firmware to firmware...
      reverse_on_value: 1.0,
      reverse_off_value: 0.0,
    }
  },
  computed: {
    servo_function_parameters(): Parameter[] {
      const params = autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
      // Sort parameters using the servo number instead of alphabetically
      const sorted = params.sort(
        (a: Parameter, b: Parameter) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }),
      )
      return sorted
    },
    vehicle_type(): string|null {
      return autopilot.vehicle_type
    },
    is_rover(): boolean {
      return autopilot.firmware_vehicle_type === FirmwareVehicleType.ArduRover
    },
    is_sub(): boolean {
      return autopilot.firmware_vehicle_type === FirmwareVehicleType.ArduSub
    },
    available_sub_motors(): MotorTestTarget[] {
      return this.servo_function_parameters.filter(
        (parameter) => parameter.value >= SERVO_FUNCTION.MOTOR1 && parameter.value <= SERVO_FUNCTION.MOTOR8,
      ).map((parameter) => {
        const servo_number = parseInt(/\d+/g.exec(parameter.name)?.[0] ?? '0', 10)
        const motor_number = parseInt(/\d+/g.exec(printParam(parameter))?.[0] ?? '0', 10)
        const name = param_value_map.Submarine[parameter.name] ?? `Motor ${motor_number}`
        const direction_parameter = autopilot_data.parameterRegex(`MOT_${motor_number}_DIRECTION`)?.[0]
        const target = motor_number - 1
        return {
          name,
          servo: servo_number,
          motor: motor_number,
          target,
          direction: direction_parameter.value,
          reverse_parameter: direction_parameter,
        }
      }).sort((a, b) => a.motor - b.motor)
    },
    available_motors(): MotorTestTarget[] {
      if (this.is_rover) {
        return this.available_rover_motors
      }
      return this.available_sub_motors
    },
    motor_direction(): {[key: number]: number} {
      const motorDict = {} as {[key: number]: number}
      const availableMotors = this.available_motors
      for (const motor of availableMotors) {
        motorDict[motor.target] = motor.direction
      }
      return motorDict
    },
    available_rover_motors(): MotorTestTarget[] {
      return this.servo_function_parameters.filter(
        (parameter) => [
          ROVER_FUNCTIONS.THROTTLE,
          ROVER_FUNCTIONS.THROTTLELEFT,
          ROVER_FUNCTIONS.THROTTLERIGHT,
          ROVER_FUNCTIONS.MAINSAIL,
          ROVER_FUNCTIONS.GROUNDSTEERING,
        ].includes(parameter.value),
      ).map((parameter) => {
        const name = printParam(parameter)
        const servo = parseInt(/\d+/g.exec(parameter.name)?.[0] ?? '0', 10)
        const target = rover_function_map[parameter.value] ?? 0
        const reverse_parameter = autopilot_data.parameterRegex(`SERVO${servo}_REVERSED`)?.[0]
        return {
          name,
          servo,
          motor: servo,
          target,
          direction: reverse_parameter.value ? -1.0 : 1.0,
          reverse_parameter,
        }
      })
    },
    motor_target_with_reversion(): {[key: number]: number} {
      const targets = { ...this.motor_targets }
      for (const motor_string of Object.keys(targets)) {
        const motor = parseInt(motor_string, 10)
        const raw_value = targets[motor] - 1500
        targets[motor] = 1500 + this.motor_direction[motor] * raw_value
      }
      return targets
    },
    vehicle_id(): number {
      return autopilot_data.system_id
    },
    is_armed(): boolean {
      const heartbeat = mavlink_store_get(
        mavlink,
        'HEARTBEAT.messageData.message',
        this.vehicle_id,
        1,
      ) as Message.Heartbeat
      return Boolean(heartbeat?.base_mode.bits & MavModeFlag.MAV_MODE_FLAG_SAFETY_ARMED)
    },
    is_manual(): boolean {
      const heartbeat = mavlink_store_get(
        mavlink,
        'HEARTBEAT.messageData.message',
        this.vehicle_id,
        1,
      ) as Message.Heartbeat

      // Legacy manual mode
      if (!(heartbeat?.base_mode.bits & MavModeFlag.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED)) {
        return Boolean(heartbeat?.base_mode.bits & MavModeFlag.MAV_MODE_FLAG_MANUAL_INPUT_ENABLED)
      }

      if (this.is_rover) {
        const rover_custom_mode_manual = 0
        return Boolean(heartbeat?.custom_mode === rover_custom_mode_manual)
      }
      if (this.is_sub) {
        const sub_custom_mode_manual = 19
        return Boolean(heartbeat?.custom_mode === sub_custom_mode_manual)
      }

      return false
    },
    arm_disarm_switch_label(): string {
      let label = `${this.is_armed ? 'Armed' : 'Disarmed'}`
      if (!this.is_manual) {
        label += ' - Vehicle needs to be in Manual Mode'
      }
      return label
    },
    motor_outputs() : {[key: number]: number} {
      const data = mavlink_store_get(mavlink, 'SERVO_OUTPUT_RAW.messageData.message') as Dictionary<number>
      const new_data = {} as {[key: number]: number}
      if (!data) {
        return {}
      }
      for (const [key, value] of Object.entries(data)) {
        if (!key.includes('servo')) continue
        const motor_name = parseInt(key.replace('servo', '').replace('_raw', ''), 10)
        new_data[motor_name] = value
      }
      return new_data
    },
    servo_output(): number[] {
      const output = Array(16)
        .fill(0)
      const data = mavlink_store_get(mavlink, 'SERVO_OUTPUT_RAW.messageData.message') as Dictionary<number> | undefined
      if (!data) {
        return output
      }
      return output
        .map((_, i) => data[`servo${i + 1}_raw`])
    },
    board_name(): string | undefined {
      return autopilot.current_board?.name
    },
    gpio_to_parameter(): Record<number, Parameter> {
      return Object.fromEntries(
        autopilot_data.parameterRegex('^.*_PIN$')
          .map((param) => [param.value, param]),
      )
    },
    servo_to_gpio(): Record<number, number> {
      const isNavigator = this.board_name?.includes('Navigator')
      return Object.fromEntries(
        Array.from({ length: 16 }, (_, i) => {
          const servo = i + 1
          if (isNavigator) {
            return [servo, servo]
          }
          if (servo <= 8) {
            return [servo, servo + 100]
          }
          return [servo, servo - 9 + 50]
        }),
      )
    },
  },
  watch: {
    is_armed() {
      // To reflect changed made from other sources like from GCSs
      this.desired_armed_state = this.is_armed
    },
    is_rover() {
      this.updateReversionValues()
    },
    is_sub() {
      this.updateReversionValues()
    },
  },
  mounted() {
    this.motor_zeroer_interval = setInterval(this.zero_motors, 300)
    this.motor_writer_interval = setInterval(this.write_motors, 100)
    fetchCurrentBoard()

    mavlink.setMessageRefreshRate({ messageName: 'SERVO_OUTPUT_RAW', refreshRate: 10 })
    this.desired_armed_state = this.is_armed
    this.installListeners()
    this.updateReversionValues()
  },
  beforeDestroy() {
    clearInterval(this.motor_zeroer_interval)
    clearInterval(this.motor_writer_interval)
    mavlink.setMessageRefreshRate({ messageName: 'SERVO_OUTPUT_RAW', refreshRate: 1 })
    this.uninstallListeners()
  },
  methods: {
    highlightMotor(motor: MotorTestTarget) {
      if (this.is_rover) {
        this.highlight = [this.stringToUserFriendlyText(printParam(this.getParam(`SERVO${motor.servo}_FUNCTION`)))]
      } else {
        this.highlight = [`Motor${motor.motor}`]
      }
    },
    convert_servo_name(name: string) {
      return name.replace('SERVO', 'Output ').replace('_FUNCTION', '')
    },
    updateReversionValues() {
      if (this.is_rover) {
        this.reverse_on_value = 1.0
        this.reverse_off_value = 0
        return
      }
      // sub
      this.reverse_on_value = -1.0
      this.reverse_off_value = 1.0
    },
    focusListener() {
      this.has_focus = true
    },
    blurListener() {
      this.has_focus = false
    },
    installListeners() {
      window.addEventListener('focus', this.focusListener)
      window.addEventListener('blur', this.blurListener)
    },
    uninstallListeners() {
      window.removeEventListener('focus', this.focusListener)
      window.removeEventListener('blur', this.blurListener)
    },
    styleForMotorBar(value: number): string {
      const percent = (value - 1500) / 10
      const left = percent < 0 ? 50 + percent : 50
      return `width: ${Math.abs(percent)}%; left: ${left}%; background-color: red`
    },
    servoToHighlight(param: Parameter): string {
      const pretty_name = this.stringToUserFriendlyText(printParam(param))
      // map for backwards compatibility
      const map: Record<string, string> = {
        Mount1Pitch: 'MountTilt',
      }
      return map[pretty_name] ?? pretty_name
    },
    showParamEdit(param: Parameter) {
      this.selected_param = param
      this.edit_param_dialog = true
    },
    parameterToUserFriendlyText(param: Parameter): string {
      if (param.value === -1) { // GPIO
        const servo_number = parseInt(/\d+/g.exec(param.name)?.[0] ?? '0', 10)
        const gpio = this.servo_to_gpio[servo_number]
        const param_using_this_gpio = this.gpio_to_parameter[gpio]
        if (param_using_this_gpio) {
          const pretty_name = param_using_this_gpio.name.split('_')[0].toLowerCase().toTitle()
          return `GPIO [${pretty_name}]`
        }
        return `GPIO ${gpio} (Unknown)`
      }
      return this.stringToUserFriendlyText(printParam(param))
    },
    stringToUserFriendlyText(text: string) {
      return param_value_map?.[this.vehicle_type ?? '']?.[text] ?? text
    },
    getParam(param: string): Parameter | undefined {
      return autopilot_data.parameter(param)
    },
    zero_motors() {
      if (!this.is_manual) {
        return
      }
      if (!this.has_focus && this.motors_zeroed) {
        return
      }
      for (const motor of this.available_motors) {
        this.motor_targets[motor.target] = 1500
      }
      this.motors_zeroed = true
    },
    async write_motors() {
      if (!this.has_focus) {
        return
      }
      if (this.is_armed && this.desired_armed_state && this.is_manual) {
        for (const [motor, value] of Object.entries(this.motor_target_with_reversion)) {
          doMotorTest(parseInt(motor, 10), value)
        }
      }
      this.motors_zeroed = false
    },
    restart_motor_zeroer() {
      clearInterval(this.motor_zeroer_interval)
      this.motor_zeroer_interval = setInterval(this.zero_motors, 500)
    },
    pause_motor_zeroer() {
      clearInterval(this.motor_zeroer_interval)
    },
    arm() {
      armDisarm(true, true).catch(() => {
        this.desired_armed_state = this.is_armed
        console.warn('Arming failed!')
      })
    },
    disarm() {
      armDisarm(false, true).catch(() => {
        this.desired_armed_state = this.is_armed
        console.warn('Disarming failed!')
      })
    },
    arm_disarm_switch_change(should_arm: boolean): void {
      // eslint-disable-next-line no-unused-expressions
      should_arm ? this.arm() : this.disarm()
    },
  },
})
</script>
<style>
.pwm-bar-content {
  align-items: center;
  display: flex;
  height: 100%;
  left: 0;
  justify-content: center;
  position: absolute;
  top: 0;
  width: 100%;
}

.pwm-bar {
    /* eslint-disable-next-line */
    background-image: linear-gradient(135deg, rgba(255, 255, 255, 0.25) 25%, transparent 0, transparent 50%,
      rgba(255, 255, 255, 0.25) 0, rgba(255, 255, 255, 0.25) 75%, transparent 0, transparent);
    background-size: 40px 40px;
    background-repeat: repeat;
    height: inherit;
    left: 0;
    position: absolute;
    transition: none;
}
.pwm-bar-bg {
  bottom: 0;
  left: 0;
  position: absolute;
  top: 0;
  transition: inherit;
  opacity: 0.3;
  width: 100%;
  background-color: rgb(195, 195, 195);
}
/* Disable transition on v-slider thumb */
.v-slider__thumb-container {
  transition:none !important;
}
</style>
