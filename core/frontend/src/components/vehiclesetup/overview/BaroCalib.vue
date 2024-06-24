<template>
  <div class="pa-1">
    <v-card class="ma-2 pa-2">
      <v-card-title class="align-center">
        Calibrate Barometer
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
                <th class="text-left">
                  Calibrated at
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="baro in baros"
                :key="baro.param"
              >
                <td><b>{{ baro.deviceName ?? 'UNKNOWN' }}</b></td>
                <td v-tooltip="'Used to estimate altitude/depth'">
                  {{ get_pressure_type[baro.param] }} Pressure
                </td>
                <td>{{ bus_name(baro.busType) }} {{ baro.bus }}</td>
                <td>{{ `0x${baro.address}` }}</td>
                <td>{{ baro_status[baro.param] }}</td>
                <td>{{ baro_ground_pressure[baro.param] }}</td>
              </tr>
            </tbody>
          </template>
        </v-simple-table>
      </v-card-text>
      <v-card-actions class="justify-center pt-4">
        {{ calibration_status }}
      </v-card-actions>
      <v-card-actions class="justify-center pa-2">
        <v-btn
          v-tooltip="'Calibrate all barometers to ground level'"
          color="primary"
          :disabled="disable_button"
          @click="calibrate"
        >
          Calibrate
        </v-btn>
      </v-card-actions>
    </v-card>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import mavlink from '@/store/mavlink'
import { printParam } from '@/types/autopilot/parameter'
import { Dictionary } from '@/types/common'
import decode, { BUS_TYPE, deviceId } from '@/utils/deviceid_decoder'
import mavlink_store_get from '@/utils/mavlink'

import { calibrator, PreflightCalibration } from '../calibration'

export default Vue.extend({
  name: 'BaroCalibrate',
  data() {
    return {
      calibration_status: '',
      disable_button: false,
    }
  },
  computed: {
    baros(): deviceId[] {
      return autopilot_data.parameterRegex('^BARO.*_DEVID')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
    baro_status(): Dictionary<string> {
      const results = {} as Dictionary<string>
      for (const baro of this.baros) {
        const radix = baro.param.replace('_DEVID', '')
        const number = parseInt(radix.replace('BARO', ''), 10)
        const msg = number === 1 ? 'SCALED_PRESSURE' : `SCALED_PRESSURE${number}`
        const value = mavlink_store_get(mavlink, `${msg}.messageData.message.press_abs`) as number
        results[baro.param] = `${value ? value.toFixed(2) : '--'} hPa`
      }
      return results
    },
    baro_ground_pressure(): Dictionary<string> {
      const results = {} as Dictionary<string>
      for (const baro of this.baros) {
        const radix = baro.param.replace('_DEVID', '')
        const calibrated_param = autopilot_data.parameter(`${radix}_GND_PRESS`)
        const pretty_value = (printParam(calibrated_param) / 100).toFixed(2)
        results[baro.param] = `${pretty_value} hPa`
      }
      return results
    },
    external_i2c_bus(): number | undefined {
      return autopilot_data.parameter('BARO_EXT_BUS')?.value
    },
    get_pressure_type(): Dictionary<string> {
      const results = {} as Dictionary<string>
      for (const baro of this.baros) {
        // BARO_SPEC_GRAV Only exist for underwater vehicles
        const spec_gravity_param = autopilot_data.parameter('BARO_SPEC_GRAV')
        const water = ['MS5837', 'MS5611', 'KELLERLD'].includes(baro.deviceName ?? '--')
        && autopilot.vehicle_type === 'Submarine' && baro.busType === BUS_TYPE.I2C
        && baro.bus === this.external_i2c_bus
        if (water) {
          results[baro.param] = printParam(spec_gravity_param)
          continue
        }
        results[baro.param] = 'Barometric'
      }
      return results
    },
  },
  methods: {
    bus_name(bus: number): string {
      return BUS_TYPE[bus]
    },
    async calibrate() {
      this.disable_button = true
      this.calibration_status = 'Starting calibration..'
      for await (const value of calibrator.calibrate(PreflightCalibration.PRESSURE)) {
        this.calibration_status = value
      }
      this.disable_button = false
    },
  },
})
</script>
