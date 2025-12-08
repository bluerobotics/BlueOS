<template>
  <div class="align-center">
    GPIOs can be used for Relays, Leak detection, and other functions not yet supported by this UI.
    This servo ({{ servo_number }}) gpio is {{ this_servo_gpio }}.

    In use by {{ function_type_using_this_gpio?.name }}

    <v-row align="end">
        <v-col cols="6">
            <span style="font-size: 1.0rem;">Change function for this servo's GPIO</span>
        </v-col>
        <v-col cols="6">
            <v-select
                v-model="selected_function_type"
                :items="options"
                item-text="text"
                item-value="value"
                return-object
                hide-details
                @change="onChange"
            />
        </v-col>
    </v-row>

  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import Parameter from '@/types/autopilot/parameter'
import autopilot from '@/store/autopilot_manager'
import autopilot_data from '@/store/autopilot'
import mavlink2rest from '@/libs/MAVLink2Rest';

export default Vue.extend({
  name: 'ServoFunctionGpioEditor',
  data() {
    return {
      selected_function_type: undefined as {text: string, value: Parameter, disabled?: boolean} | undefined,
    }
  },
  props: {
    param: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  methods: {
    isSupportedParam(param: Parameter): boolean {
        return param.name.includes('RELAY') || param.name.includes('LEAK')
    },
    onChange(value: {text: string, value: Parameter}) {
        const is_relay = value.value.name.includes('RELAY')
        const is_leak = value.value.name.includes('LEAK')
        if (!this.this_servo_gpio) {
            console.warn('No GPIO found for servo', this.servo_number)
            return
        }
        if (!is_relay && !is_leak) {
            // Unsupported parameter type, don't handle
            return
        }
        if (is_relay) {
            mavlink2rest.setParam(value.value.name, 1 /* Relay */, autopilot_data.system_id, value.value.paramType.type)
            const pin_param_name = value.value.name.replace('FUNCTION', 'PIN')
            mavlink2rest.setParam(pin_param_name, this.this_servo_gpio, autopilot_data.system_id, 'MAV_PARAM_TYPE_INT8')
            if (this.function_pin_parameter_using_this_gpio) {
                mavlink2rest.setParam(this.function_pin_parameter_using_this_gpio.name, -1, autopilot_data.system_id, 'MAV_PARAM_TYPE_INT8')
            }
        }
        if (is_leak) {
            mavlink2rest.setParam(value.value.name, 1 /* Digital */, autopilot_data.system_id, value.value.paramType.type)
            const pin_param_name = value.value.name.replace('TYPE', 'PIN')
            mavlink2rest.setParam(pin_param_name, this.this_servo_gpio, autopilot_data.system_id, 'MAV_PARAM_TYPE_INT8')
            if (this.function_pin_parameter_using_this_gpio) {
                mavlink2rest.setParam(this.function_pin_parameter_using_this_gpio.name, -1, autopilot_data.system_id, 'MAV_PARAM_TYPE_INT8')
            }
        }
    },
  },
  computed: {
    pin_parameters(): Parameter[] {
      return autopilot_data.parameterRegex(`^.*_PIN$`) as Parameter[]
    },
    servo_number(): number | undefined {
      const option_name = this.param.name.match(/SERVO(\d+)_FUNCTION/)?.[1]
      return option_name ? parseInt(option_name) : undefined
    },
    board_name(): string | undefined {
      return autopilot.current_board?.name
    },
    this_servo_gpio(): number | undefined {
      if (!this.servo_number) return undefined
      if (this.board_name?.startsWith('Navigator')) {
        return this.servo_number
      }
      // We are assuming most boards follow the same GPIO numbering scheme as the Pixhawk1
      // Aux channels start at 50, and Main channels start at 101

      if (this.servo_number <= 8) {
        return this.servo_number + 100
      }
      return this.servo_number - 9 + 50
    },
    function_pin_parameter_using_this_gpio(): Parameter | undefined {
        return this.pin_parameters.find((param) => param.value === this.this_servo_gpio)
    },
    function_type_using_this_gpio(): Parameter | undefined {
        const param_name = this.function_pin_parameter_using_this_gpio?.name.split('_')[0]
        let new_param_name: string | undefined = undefined
        if (param_name?.includes('RELAY')) {
            new_param_name = param_name + '_FUNCTION'
        }
        if (param_name?.includes('LEAK')) {
            new_param_name = param_name + '_TYPE'
        }
        return new_param_name ? autopilot_data.parameter(new_param_name as string) : this.function_pin_parameter_using_this_gpio
    },
    relay_parameters(): Parameter[] {
      return autopilot_data.parameterRegex('^RELAY(\\d+)_FUNCTION$') as Parameter[]
    },
    leak_parameters(): Parameter[] {
      return autopilot_data.parameterRegex('^LEAK(\\d+)_TYPE$') as Parameter[]
    },
    options(): {text: string, value: Parameter, disabled?: boolean}[] {
      const supportedOptions: {text: string, value: Parameter, disabled?: boolean}[] = [...this.relay_parameters, ...this.leak_parameters].map((param) => {
        return {
          text: param.name.split('_')[0].toLowerCase().toTitle(),
          value: param,
        }
      })
      // If the current GPIO is used by an unsupported parameter, add it to the options
      if (this.function_pin_parameter_using_this_gpio && !this.isSupportedParam(this.function_pin_parameter_using_this_gpio)) {
        supportedOptions.unshift({
          text: `${this.function_pin_parameter_using_this_gpio.name} (not supported)`,
          value: this.function_pin_parameter_using_this_gpio,
          disabled: true,
        })
      }
      return supportedOptions
    },
  },
  watch: {
    function_type_using_this_gpio: {
        handler(new_value: Parameter | undefined) {
            if (!new_value) {
                this.selected_function_type = undefined
                return
            }
            const isSupported = this.isSupportedParam(new_value)
            this.selected_function_type = {
                text: isSupported
                    ? new_value.name.split('_')[0].toLowerCase().toTitle()
                    : `${new_value.name} (not supported)`,
                value: new_value,
            }
        },
        immediate: true,
    },
  },
})
</script>
