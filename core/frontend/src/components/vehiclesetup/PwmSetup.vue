<template>
  <div>
    <v-row class="mt-5">
      <v-col
        cols="12"
        sm="8"
      >
        <v-card>
          <vehicle-viewer :highlight="highlight" />
        </v-card>
        <v-card class="mt-3">
          <v-simple-table
            v-tooltip="'Not Implemented'"
            dense
          >
            <template #default>
              <thead>
                <tr>
                  <th class="text-left">
                    Motor Test
                  </th>
                  <th />
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="motor of available_motors"
                  :key="'mot' + motor.name"
                  @mouseover="highlight = printParam(motor)"
                  @mouseleave="highlight = null"
                >
                  <td>{{ printParam(motor) }}</td>
                  <td>
                    <v-slider
                      hide-details
                      :min="1000"
                      :max="2000"
                      value="1500"
                      disabled
                    />
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
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in servo_function_parameters"
                  :key="item.name"
                  style="cursor: pointer;"
                  @mouseover="highlight = stringToUserFriendlyText(printParam(item))"
                  @mouseleave="highlight = null"
                  @click="showParamEdit(item)"
                >
                  <td>{{ item.name }}</td>
                  <td>{{ stringToUserFriendlyText(printParam(item)) }}</td>
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
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter, { printParam } from '@/types/autopilot/parameter'
import { SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'
import { Dictionary } from '@/types/common'

const param_value_map = {
  Submarine: {
    RCIN8: 'Lights 1',
    RCIN9: 'Lights 2',
    RCIN10: 'Video Switch',
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
      highlight: null as string | null,
      edit_param_dialog: false,
      param: undefined as Parameter | undefined,
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
    vehicle_type() {
      return autopilot.vehicle_type
    },
    available_motors(): Parameter[] {
      return this.servo_function_parameters.filter(
        (parameter) => parameter.value >= SERVO_FUNCTION.MOTOR1 && parameter.value <= SERVO_FUNCTION.MOTOR8,
      )
    },
  },
  methods: {
    showParamEdit(param: Parameter) {
      this.param = param
      this.edit_param_dialog = true
    },
    stringToUserFriendlyText(text: string) {
      return param_value_map?.[this.vehicle_type ?? '']?.[text] ?? text
    },
    printParam,
  },
})
</script>
