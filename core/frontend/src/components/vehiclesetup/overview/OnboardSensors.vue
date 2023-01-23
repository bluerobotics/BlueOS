<template>
  <v-card class="ma-2">
    <v-card-title class="align-center">
      Autopilot Sensors
    </v-card-title>
    <v-card-text>
      <v-simple-table dense>
        <template #default>
          <thead>
            <tr>
              <th class="text-left">
                Sensor
              </th>
              <th class="text-left">
                Type
              </th>
              <th class="text-left">
                Bus
              </th>
              <th class="text-left">
                Address
              </th>
              <th class="text-left">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="imu in imus"
              :key="imu.param"
            >
              <td><b>{{ imu.deviceName ?? 'UNKNOWN' }}</b></td>
              <td v-tooltip="'Inertial Navigation Sensor'">
                INS
              </td>
              <td>{{ imu.busType }} {{ imu.bus }}</td>
              <td>{{ `0x${imu.address}` }}</td>
              <td>{{ imu_is_calibrated(imu) ? 'Calibrated' : 'Needs Calibration' }}</td>
            </tr>
            <tr
              v-for="compass in compasses"
              :key="compass.param"
            >
              <td><b>{{ compass.deviceName ?? 'UNKNOWN' }}</b></td>
              <td>Compass</td>
              <td>{{ compass.busType }} {{ compass.bus }}</td>
              <td>{{ `0x${compass.address}` }}</td>
              <td>{{ compass_is_calibrated(compass) ? 'Calibrated' : 'Needs Calibration' }}</td>
            </tr>
            <tr
              v-for="baro in baros"
              :key="baro.param"
            >
              <td><b>{{ baro.deviceName ?? 'UNKNOWN' }}</b></td>
              <td v-tooltip="'Used to estimate altitude/depth'">
                {{ get_pressure_type(baro) }} Pressure
              </td>
              <td>{{ baro.busType }} {{ baro.bus }}</td>
              <td>{{ `0x${baro.address}` }}</td>
              <td>{{ baro_status(baro) }}</td>
            </tr>
          </tbody>
        </template>
      </v-simple-table>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import mavlink from '@/store/mavlink'
import { printParam } from '@/types/autopilot/parameter'
import { parameters_service } from '@/types/frontend_services'
import decode, { deviceId } from '@/utils/deviceid_decoder'
import mavlink_store_get from '@/utils/mavlink'

const notifier = new Notifier(parameters_service)

export default Vue.extend({
  name: 'OnboardSensors',
  computed: {
    imus() : deviceId[] {
      return autopilot_data.parameterRegex('^INS_ACC.*_ID')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
    compasses(): deviceId[] {
      return autopilot_data.parameterRegex('^COMPASS_DEV_ID.*')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
    baros(): deviceId[] {
      return autopilot_data.parameterRegex('^BARO.*_DEVID')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
  },
  mounted() {
    mavlink.setMessageRefreshRate({ messageName: 'SCALED_PRESSURE', refreshRate: 1 })
    mavlink.setMessageRefreshRate({ messageName: 'SCALED_PRESSURE2', refreshRate: 1 })
    mavlink.setMessageRefreshRate({ messageName: 'VFR_HUD', refreshRate: 1 })
  },
  methods: {
    imu_is_calibrated(imu: deviceId) {
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
      return offset_params.isEmpty() || scale_params.isEmpty() || !is_at_default_offsets || !is_at_default_scale
    },
    is_water_baro(baro: deviceId) {
      if (['MS5837', 'MS5611', 'KELLERLD'].includes(baro?.deviceName ?? '--')
      && autopilot.vehicle_type === 'Submarine') {
        return true
      }
      return false
    },
    compass_is_calibrated(imu: deviceId) {
      const compass_number = imu.param.split('COMPASS_DEV_ID')[1]
      const offset_params_names = [
        `COMPASS_OFS${compass_number}_X`,
        `COMPASS_OFS${compass_number}_Y`,
        `COMPASS_OFS${compass_number}_Z`,
      ]
      const diagonal_params_names = [
        `COMPASS_ODI${compass_number}_X`,
        `COMPASS_ODI${compass_number}_Y`,
        `COMPASS_ODI${compass_number}_Z`,
      ]

      const offset_params = offset_params_names.map(
        (name) => autopilot_data.parameter(name),
      )
      const diagonal_params = diagonal_params_names.map(
        (name) => autopilot_data.parameter(name),
      )
      if (offset_params.includes(undefined) || diagonal_params.includes(undefined)) {
        notifier.pushError('PARAM_MISSING', 'Unable to find Compass parameters')
      }

      const scale_param_name = `COMPASS_SCALE${compass_number}`
      const scale_param = autopilot_data.parameter(scale_param_name)
      const is_at_default_offsets = offset_params.every((param) => param?.value === 0.0)
      const is_at_default_diagonals = diagonal_params.every((param) => param?.value === 0.0)
      return offset_params.isEmpty() || diagonal_params.isEmpty()
        || !is_at_default_offsets || !is_at_default_diagonals || scale_param?.value !== 0.0
    },
    baro_status(baro: deviceId) {
      const radix = baro.param.replace('_DEVID', '')
      const number = parseInt(radix.replace('BARO', ''), 10)
      if (this.is_water_baro(baro)) {
        const value = mavlink_store_get(mavlink, 'VFR_HUD.messageData.message.alt') as number
        return `${value ? value.toFixed(2) : '--'} m`
      }
      const msg = number === 1 ? 'SCALED_PRESSURE' : `SCALED_PRESSURE${number}`
      const value = mavlink_store_get(mavlink, `${msg}.messageData.message.press_abs`) as number
      return `${value ? value.toFixed(2) : '--'} hPa`
    },
    get_pressure_type(baro: deviceId) {
      if (!this.is_water_baro(baro)) {
        return 'Barometric'
      }
      const spec_gravity_param = autopilot_data.parameter('BARO_SPEC_GRAV')

      return `${printParam(spec_gravity_param)}`
    },
  },
})
</script>
