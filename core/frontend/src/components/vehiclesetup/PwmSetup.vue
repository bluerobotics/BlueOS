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
                  v-for="motnumber of available_motors"
                  :key="'mot' + motnumber"
                  @mouseover="highlight = `Motor${motnumber}`"
                  @mouseleave="highlight = null"
                >
                  <td>Motor{{ motnumber }}</td>
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
                  @mouseover="highlight = stringToUserFriendlyText(printParam(item))"
                  @mouseleave="highlight = null"
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
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter, { printParam } from '@/types/autopilot/parameter'
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
    VehicleViewer,
  },
  data() {
    return {
      highlight: null as string | null,
    }
  },
  computed: {
    servo_function_parameters(): Parameter[] {
      const params = autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
      // Sort parameters using the servo number instead of alphabetically
      const sorted = params.sort(
        (a: Parameter, b: Parameter) => a.name.localeCompare(
          b.name, undefined, { numeric: true, sensitivity: 'base' },
        ),
      )
      return sorted
    },
    vehicle_type() {
      return autopilot.vehicle_type
    },
    available_motors() {
      // TODO: per-frame motor count, maybe dynamic?
      return [...Array(9).keys()].splice(1)
    },
  },
  methods: {
    stringToUserFriendlyText(text: string) {
      return param_value_map?.[this.vehicle_type ?? '']?.[text] ?? text
    },
    printParam,
  },
})
</script>
