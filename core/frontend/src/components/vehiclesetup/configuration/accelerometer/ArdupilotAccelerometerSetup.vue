<template>
  <div class="d-flex flex-col justify-center">
    <v-card v-if="params_finished_loaded" outline class="pa-5 mt-4 mr-2 mb-2">
      <v-simple-table>
        <thead>
          <tr>
            <th>IMU</th>
            <th>Calibration</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="imu in imus" :key="imu.deviceIdNumber">
            <td>{{ imu.deviceName }}</td>
            <td>
              <v-icon
                v-if="imu_is_calibrated[imu.param]"
                v-tooltip="'Sensor is calibrated and good to use'"
                color="green"
              >
                mdi-emoticon-happy-outline
              </v-icon>
              <v-icon
                v-else
                v-tooltip="'Sensor needs to be calibrated'"
                color="red"
              >
                mdi-emoticon-sad-outline
              </v-icon>
              {{ imu_is_calibrated[imu.param] ? 'Calibrated' : 'Needs calibration' }}
              <v-icon
                v-if="imu_temperature_is_calibrated[imu.param].calibrated"
                v-tooltip="`Sensor was calibrated at ${getCalibrationTemperature(imu)} ºC`"
                color="green"
              >
                mdi-thermometer-check
              </v-icon>
              <v-icon
                v-else
                v-tooltip="'Sensor thermometer needs to be calibrated'"
                color="red"
              >
                mdi-thermometer-off
              </v-icon>
            </td>
          </tr>
        </tbody>
      </v-simple-table>
      <v-card-actions class="justify-center">
        <FullAccelerometerCalibration />
        <QuickAccelerometerCalibration />
      </v-card-actions>
    </v-card>
    <spinning-logo
      v-else
      size="50%"
      :subtitle="`${loaded_params}/${total_params} parameters loaded`"
    />
  </div>
</template>
<script lang="ts">
import Vue from 'vue'

// eslint-disable-next-line
import FullAccelerometerCalibration from '@/components/vehiclesetup/configuration/accelerometer/FullAccelerometerCalibration.vue'
import autopilot_data from '@/store/autopilot'
import { Dictionary } from '@/types/common'
import decode, { deviceId } from '@/utils/deviceid_decoder'

import QuickAccelerometerCalibration from './QuickAccelerometerCalibration.vue'

export default Vue.extend({
  name: 'ArdupilotAccelerometerSetup',
  components: {
    FullAccelerometerCalibration,
    QuickAccelerometerCalibration,
  },
  data() {
    return {
    }
  },
  computed: {
    params_finished_loaded(): boolean {
      return autopilot_data.finished_loading
    },
    loaded_params(): number {
      return autopilot_data.parameters_loaded
    },
    total_params(): number {
      return autopilot_data.parameters_total
    },
    imus() : deviceId[] {
      return autopilot_data.parameterRegex('^INS_ACC.*_ID')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
    // TODO: refactor, same code as OnboardSensors.vue
    imu_is_calibrated(): Dictionary<boolean> {
      const results = {} as Dictionary<boolean>
      for (const imu of this.imus) {
        const param_radix = imu.param.split('_ID')[0]
        const offset_params_names = [`${param_radix}OFFS_X`, `${param_radix}OFFS_Y`, `${param_radix}OFFS_Z`]
        const scale_params_names = [`${param_radix}SCAL_X`, `${param_radix}SCAL_Y`, `${param_radix}SCAL_Z`]
        const offset_params = offset_params_names.map(
          (name) => autopilot_data.parameter(name),
        )
        const scale_params = scale_params_names.map(
          (name) => autopilot_data.parameter(name),
        )
        const is_at_default_offsets = offset_params.every((param) => param?.value === 0.0)
        const is_at_default_scale = scale_params.every((param) => param?.value === 1.0)
        results[imu.param] = offset_params.isEmpty() || scale_params.isEmpty()
        || !is_at_default_offsets || !is_at_default_scale
      }
      return results
    },
    imu_temperature_is_calibrated(): Dictionary<{ calibrated: boolean, calibrationTemperature: number }> {
      const results = {} as Dictionary<{ calibrated: boolean, calibrationTemperature: number }>
      for (const imu of this.imus) {
        let param_radix = imu.param.split('_ID')[0]
        // CALTEMP parameters contains ID for the first sensor, _ID does not, so we need to add it
        if (!/\d$/.test(param_radix)) {
          param_radix += '1'
        }
        const name = `${param_radix}_CALTEMP`
        const parameter = autopilot_data.parameter(name)
        results[imu.param] = {
          calibrated: parameter !== undefined && parameter.value !== -300,
          calibrationTemperature: parameter?.value ?? 0,
        }
      }
      return results
    },
  },
  methods: {
    getCalibrationTemperature(imu: deviceId) {
      return this.imu_temperature_is_calibrated[imu.param].calibrationTemperature.toFixed(0)
    },
  },
})
</script>
<style scoped="true">
td {
  padding-left: 5px !important;
  padding-right: 5px !important;
}
</style>
