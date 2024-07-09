<template>
  <div class="main-container">
    <v-card outline class="pa-2" width="600px">
      <v-card-title class="align-center justify-center">
        Calibrate Gyroscopes
      </v-card-title>
      <v-card-text>
        A calibrated gyro should display a value of 0 on all axes when the vehicle is stationary.
        Symptoms of a mis-calibrated gyro include yaw drift and small attitude offsets.
      </v-card-text>
      <v-card-text>
        <v-simple-table>
          <thead>
            <tr>
              <th>IMU</th>
              <th>Angular speed (mrad/s)</th>
              <th>Offsets (mrad/s)</th>
              <th>Calibration temperature (°C)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in valid_table_items" :key="item.name">
              <td>{{ item.name }}</td>
              <td>{{ item.value }}</td>
              <td style="min-width: 150px;">
                {{ renderVec3(item.offsets) }}
              </td>
              <td>{{ item.calibration_temperature?.toFixed(1) }}</td>
            </tr>
          </tbody>
        </v-simple-table>
      </v-card-text>
      <v-card-text>
        The Gyroscopes can be automatically calibrated at startup. Be mindful that this is not recommended for
        vehicles that start up on moving platforms (such as boats).
        <div class="ma-5 pa-5">
          <inline-parameter-editor
            v-if="ins_gyr_cal"
            :param="ins_gyr_cal"
            :label="'Calibrate gyroscopes automaicallly'"
          />
        </div>
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn
          color="primary"
          @click="calibrate"
        >
          Calibrate Gyroscopes
        </v-btn>
      </v-card-actions>
      <v-card-actions class="justify-center">
        {{ calibration_status }}
      </v-card-actions>
    </v-card>
  </div>
</template>

<script lang="ts">
import { vec3 } from 'gl-matrix'
import Vue from 'vue'

import InlineParameterEditor from '@/components/parameter-editor/InlineParameterEditor.vue'
import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import Parameter from '@/types/autopilot/parameter'
import { Dictionary } from '@/types/common'
import decode from '@/utils/deviceid_decoder'
import mavlink_store_get from '@/utils/mavlink'

import { calibrator, PreflightCalibration } from '../calibration'

interface CalibrationStatus {
    param?: Parameter
    name: string
    value: vec3|null
    offsets: vec3|null
    calibration_temperature: number|null
}
export default Vue.extend({
  name: 'GyroCalibrate',
  components: {
    InlineParameterEditor,
  },
  data() {
    return {
      calibration_status: '',
    }
  },
  computed: {
    table_items(): CalibrationStatus[] {
      return [1, 2, 3].map((index) => {
        const suffix = index === 1 ? '' : index.toString()
        const gyrId = autopilot_data.parameter(`INS_GYR${suffix}_ID`)
        const offsets = ['X', 'Y', 'Z'].map((axis) => {
          const rawValue = autopilot_data.parameter(`INS_GYROFFS${suffix}_${axis}`)?.value
          return rawValue ? rawValue * 1000 : null
        }) as [number, number, number]

        return {
          name: gyrId ? decode(gyrId.name, gyrId.value).deviceName ?? '?' : '?',
          param: gyrId,
          value: this[`gyro_read${index}`],
          offsets: vec3.fromValues(...offsets),
          calibration_temperature: autopilot_data.parameter(`INS_GYR${index}_CALTEMP`)?.value ?? 0,
        }
      })
    },
    valid_table_items(): CalibrationStatus[] {
      return this.table_items.filter((item: CalibrationStatus) => item.param?.value !== 0)
    },
    ins_gyr_cal(): Parameter | undefined {
      return autopilot_data.parameter('INS_GYR_CAL')
    },
    gyro_read1(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'RAW_IMU.messageData.message') as Dictionary<number>
      if (!msg) return null
      return vec3.fromValues(msg.xgyro, msg.ygyro, msg.zgyro)
    },
    gyro_read2(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'SCALED_IMU2.messageData.message') as Dictionary<number>
      if (!msg) return null
      return vec3.fromValues(msg.xgyro, msg.ygyro, msg.zgyro)
    },
    gyro_read3(): vec3 | null {
      const msg = mavlink_store_get(mavlink, 'SCALED_IMU3.messageData.message') as Dictionary<number>
      if (!msg) return null
      return vec3.fromValues(msg.xgyro, msg.ygyro, msg.zgyro)
    },
  },
  mounted() {
    for (const msg of ['RAW_IMU', 'SCALED_IMU2', 'SCALED_IMU3']) {
      mavlink.setMessageRefreshRate({ messageName: msg, refreshRate: 10 })
    }
  },
  methods: {
    async calibrate() {
      this.calibration_status = 'Calibrating...'
      for await (const value of calibrator.calibrate(PreflightCalibration.GYROSCOPE)) {
        this.calibration_status = value
      }
    },
    renderVec3(value: vec3 | null): string {
      if (!value) {
        return 'N/A'
      }
      return [value[0], value[1], value[2]].map((v) => v.toFixed(2)).join(', ')
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
</style>
