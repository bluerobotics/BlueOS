<template>
  <div class="main-container">
    <v-card outline class="pa-2">
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
  </div>
</template>
<script lang="ts">
import Vue from 'vue'

// eslint-disable-next-line
import FullAccelerometerCalibration from '@/components/vehiclesetup/configuration/accelerometer/FullAccelerometerCalibration.vue'
import autopilot_data from '@/store/autopilot'
import { Dictionary } from '@/types/common'
import decode, { deviceId } from '@/utils/deviceid_decoder'

import { imu_is_calibrated, imu_temperature_is_calibrated } from '../common'
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
    imus() : deviceId[] {
      return autopilot_data.parameterRegex('^INS_ACC.*_ID')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
    imu_is_calibrated(): Dictionary<boolean> {
      return imu_is_calibrated(this.imus, autopilot_data)
    },
    imu_temperature_is_calibrated(): Dictionary<{ calibrated: boolean, calibrationTemperature: number }> {
      return imu_temperature_is_calibrated(this.imus, autopilot_data)
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
.main-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
}

td {
  padding-left: 5px !important;
  padding-right: 5px !important;
}

</style>
