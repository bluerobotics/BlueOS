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
          <tr v-for="accelerometer in ardupilot_sensors.accelerometers" :key="accelerometer.deviceIdNumber">
            <td>{{ accelerometer.deviceName }}</td>
            <td>
              <v-icon
                v-if="ardupilot_sensors.accelerometers_calibrated[accelerometer.param]"
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
              {{ ardupilot_sensors.accelerometers_calibrated[accelerometer.param]
                ? 'Calibrated'
                : 'Needs calibration' }}
              <v-icon
                v-if="ardupilot_sensors.accelerometers_temperature_calibrated[accelerometer.param].calibrated"
                v-tooltip="`Sensor was calibrated at ${getCalibrationTemperature(accelerometer)} ºC`"
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
import ardupilot_sensors, { ArdupilotSensorsStore } from '@/store/ardupilot_sensors'
import { deviceId } from '@/utils/deviceid_decoder'

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
    ardupilot_sensors(): ArdupilotSensorsStore {
      return ardupilot_sensors
    },
  },
  methods: {
    getCalibrationTemperature(imu: deviceId) {
      return ardupilot_sensors.accelerometers_temperature_calibrated[imu.param].calibrationTemperature.toFixed(0)
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
