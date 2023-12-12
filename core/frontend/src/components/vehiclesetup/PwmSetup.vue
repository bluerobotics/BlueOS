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
                  <th>
                    <v-switch
                      v-model="desired_armed_state"
                      :loading="desired_armed_state !== (is_armed) ? 'warning' : null"
                      :disabled="!is_manual"
                      class="mx-1 flex-grow-0"
                      :label="arm_disarm_switch_label"
                      :color="`${is_armed ? 'error' : 'success'}`"
                      @change="arm_disarm_switch_change"
                    />
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
                  @mouseover="highlight = [
                    stringToUserFriendlyText(printParam(getParam(`SERVO${motor.servo}_FUNCTION`))),
                  ]"
                  @mouseleave="highlight = default_highlight"
                >
                  <td width="20%">
                    {{ motor.name }}
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
                  @mouseover="highlight = [stringToUserFriendlyText(printParam(item))]"
                  @mouseleave="highlight = default_highlight"
                  @click="showParamEdit(item)"
                >
                  <td>{{ item.name }}</td>
                  <td>{{ stringToUserFriendlyText(printParam(item)) }}</td>
                  <td>{{ servo_output[index] }}</td>
                </tr>
              </tbody>
            </template>
          </v-simple-table>
        </v-card>
      </v-col>
    </v-row>
    <parameter-editor-dialog
      v-model="edit_param_dialog"
      :param="param"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import ParameterEditorDialog from '@/components/parameter-editor/ParameterEditorDialog.vue'
import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import {
  MavCmd, MavModeFlag,
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
import mavlink_store_get from '@/utils/mavlink'

interface MotorTestTarget {
  name: string
  servo: number // target and servo differ in rover
  target: number
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
    ParameterEditorDialog,
    VehicleViewer,
  },
  data() {
    return {
      highlight: ['Motor', 'Light', 'Mount', 'Gripper'],
      default_highlight: ['Motor', 'Light', 'Mount', 'Gripper'],
      edit_param_dialog: false,
      param: undefined as Parameter | undefined,
      motor_targets: {} as {[key: number]: number},
      motor_zeroer_interval: undefined as undefined | number,
      motor_writer_interval: undefined as undefined | number,
      desired_armed_state: false,
      arming_timeout: undefined as number | undefined,
      has_focus: true,
      motors_zeroed: false,
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
        const number = parseInt(/\d+/g.exec(parameter.name)?.[0] ?? '0', 10)
        const name = param_value_map.Submarine[parameter.name] ?? `Motor ${number}`
        const target = number - 1
        return {
          name,
          servo: number,
          target,
        }
      })
    },
    available_motors(): MotorTestTarget[] {
      if (this.is_rover) {
        return this.available_rover_motors
      }
      return this.available_sub_motors
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
        return {
          name,
          servo,
          target,
        }
      })
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
  },
  watch: {
    is_armed() {
      // To reflect changed made from other sources like from GCSs
      this.desired_armed_state = this.is_armed
    },
  },
  mounted() {
    this.motor_zeroer_interval = setInterval(this.zero_motors, 300)
    this.motor_writer_interval = setInterval(this.write_motors, 100)
    mavlink.setMessageRefreshRate({ messageName: 'SERVO_OUTPUT_RAW', refreshRate: 10 })
    this.desired_armed_state = this.is_armed
    this.installListeners()
  },
  beforeDestroy() {
    clearInterval(this.motor_zeroer_interval)
    clearInterval(this.motor_writer_interval)
    mavlink.setMessageRefreshRate({ messageName: 'SERVO_OUTPUT_RAW', refreshRate: 1 })
    this.uninstallListeners()
  },
  methods: {
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
    showParamEdit(param: Parameter) {
      this.param = param
      this.edit_param_dialog = true
    },
    stringToUserFriendlyText(text: string) {
      return param_value_map?.[this.vehicle_type ?? '']?.[text] ?? text
    },
    getParam(param: string): Parameter | undefined {
      return autopilot_data.parameter(param)
    },
    printParam,
    zero_motors() {
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
      if (this.is_armed && this.desired_armed_state) {
        for (const [motor, value] of Object.entries(this.motor_targets)) {
          this.doMotorTest(parseInt(motor, 10), value)
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
      this.armDisarm(true, true)
      this.arming_timeout = setTimeout(() => {
        if (this.desired_armed_state === this.is_armed) return
        this.desired_armed_state = this.is_armed
        console.warn('Arming failed!')
      }, 5000)
    },
    disarm() {
      this.armDisarm(false, true)
      this.arming_timeout = setTimeout(() => {
        if (this.desired_armed_state === this.is_armed) return
        this.desired_armed_state = this.is_armed
        console.warn('Disarming failed!')
      }, 5000)
    },
    arm_disarm_switch_change(should_arm: boolean): void {
      // eslint-disable-next-line no-unused-expressions
      should_arm ? this.arm() : this.disarm()
    },
    armDisarm(arm: boolean, force: boolean): void {
      mavlink2rest.sendMessage(
        {
          header: {
            system_id: 255,
            component_id: 0,
            sequence: 0,
          },
          message: {
            type: 'COMMAND_LONG',
            param1: arm ? 1 : 0, // 0: Disarm, 1: ARM,
            param2: force ? 21196 : 0, // force arming/disarming (override preflight checks and disarming in flight)
            param3: 0,
            param4: 0,
            param5: 0,
            param6: 0,
            param7: 0,
            command: {
              type: MavCmd.MAV_CMD_COMPONENT_ARM_DISARM,
            },
            target_system: autopilot_data.system_id,
            target_component: 1,
            confirmation: 0,
          },
        },
      )
    },
    async doMotorTest(motorId: number, output: number): Promise<void> {
      mavlink2rest.sendMessageViaWebsocket(
        {
          header: {
            system_id: 255,
            component_id: 0,
            sequence: 0,
          },
          message: {
            type: 'COMMAND_LONG',
            // Rover and Sub have different starting numbers for motors
            param1: motorId, // MOTOR_TEST_ORDER
            param2: 1, // MOTOR_TEST_THROTTLE_PWM
            param3: output,
            param4: 1, // Seconds running the motor
            param5: 1, // Number of motors to be tested
            param6: 2, // Motor numbers are specified as the output as labeled on the board.
            param7: 0,
            command: {
              type: MavCmd.MAV_CMD_DO_MOTOR_TEST,
            },
            target_system: autopilot_data.system_id,
            target_component: 1,
            confirmation: 0,
          },
        },
      )
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
