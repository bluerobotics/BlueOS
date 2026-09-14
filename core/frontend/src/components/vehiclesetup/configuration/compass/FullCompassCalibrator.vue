<template>
  <v-dialog
    v-model="dialog"
    width="600"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        v-bind="attrs"
        v-on="on"
      >
        Start Full Calibration
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5 grey lighten-2 black--text">
        Onboard Compass Calibration
      </v-card-title>
      <v-card-text class="pa-10">
        <span v-if="state === states.IDLE">
          <p>
            <strong>Onboard Compass Calibration</strong> is the regular calibration used
            for ArduPilot vehicles.
            It requires spinning the vehicle around all axes, which allows it to calibrate the
            readings to the expected local magnetic field.
          </p>
          <p>
            A valid global region/position is <strong>recomended</strong> for Onboard Calibration to
            estimate the local world magnetic field.
          </p>
        </span>
        <span v-else-if="state === states.CALIBRATING">
          Spin your vehicle around all of its axes until the progress bar completes.
          The arrow is the field as the vehicle currently measures it, so it drifts a little while the
          compass is still uncalibrated.
          Bring the grey sections onto the arrow, each one lights up once it has been sampled.
        </span>

        <auto-coordinate-detector
          v-if="state === states.IDLE"
          v-model="coordinates"
        />
        <compass-mask-picker v-if="state === states.IDLE" v-model="compass_mask" :devices="compasses" />
        <v-divider />
        <v-alert
          v-if="status_text"
          :type="status_type"
        >
          {{ status_text }}
        </v-alert>
        <v-simple-table v-if="Object.keys(fitness).length">
          <thead>
            <th>Compass</th>
            <th>
              Fitness (mGauss)
            </th>
          </thead>
          <tbody>
            <tr v-for="(fit, compass) of fitness" :key="compass">
              <td>{{ compass }}</td>
              <td>
                <calibrationQualityIndicator :quality="fit" />
              </td>
            </tr>
          </tbody>
        </v-simple-table>
        <compass-calibration-progress-grid
          v-if="state === states.CALIBRATING && completion_mask.length > 0"
          :completion-mask="completion_mask"
          :direction-x="field_direction.x"
          :direction-y="field_direction.y"
          :direction-z="field_direction.z"
          :roll="attitude.roll"
          :pitch="attitude.pitch"
          :yaw="attitude.yaw"
        />

        <v-progress-linear
          v-if="percent && !all_compasses_calibrated"
          v-model="percent"
          color="blue-grey"
          height="25"
          class="mt-5 mb-5"
        >
          <template #default="{ value }">
            <strong>{{ Math.ceil(value) }}%</strong>
          </template>
        </v-progress-linear>

        <StatusTextWatcher :filter="/.*/" :style="`display : ${status_type === 'error' ? 'block' : 'none'};`" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn
          v-if="state !== states.CALIBRATING && state !== states.FAILED"
          color="primary"
          :disabled="!compass_mask || !coordinates"
          @click="calibrate()"
        >
          Calibrate
        </v-btn>
        <v-btn v-if="state === states.DONE" color="primary" @click="dismiss">
          Dismiss
        </v-btn>
        <RebootButton />
        <v-btn v-if="state == states.CALIBRATING" color="red" @click="cancelCalibration()">
          Cancel
        </v-btn>
        <v-btn v-if="state == states.FAILED" color="primary" @click="reset()">
          Ok
        </v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import RebootButton from '@/components/utils/RebootButton.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'
import { MavCmd, MAVLinkType, MavResult } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import { Dictionary } from '@/types/common'
import { deviceId } from '@/utils/deviceid_decoder'
import mavlink_store_get from '@/utils/mavlink'

import CalibrationQualityIndicator from './CalibrationQualityIndicator.vue'

// The field the samples are binned by, and the attitude the grid is drawn at
const GRID_MESSAGES = ['ATTITUDE', 'RAW_IMU']
const GRID_REFRESH_RATE = 10

enum states {
  IDLE,
  CALIBRATING,
  DONE,
  FAILED,
}

export default {
  name: 'FullCompassCalibrator',
  components: {
    CalibrationQualityIndicator,
    RebootButton,
  },
  props: {
    compasses: {
      type: Array as PropType<deviceId[]>,
      required: true,
    },
  },
  data() {
    return {
      dialog: false,
      coordinates: undefined as { lat: number, lon: number } | undefined,
      compass_mask: 0,
      status_type: '' as string | undefined,
      status_text: '' as string | undefined,
      percent: 0,
      completion_mask: [] as number[],
      progress_compass_id: undefined as number | undefined,
      field_subscribed: false,
      state: states.IDLE,
      progress_listener: undefined as Listener | undefined,
      report_listener: undefined as Listener | undefined,
      fitness: {} as Dictionary<number>,
    }
  },
  computed: {
    states() {
      return states
    },
    compasses_calibrated(): number {
      return Object.keys(this.fitness).length
    },
    all_compasses_calibrated(): boolean {
      return this.compasses_calibrated === this.compasses.length
    },
    // MAG_CAL_PROGRESS carries a direction field, but ArduPilot always sends it as zero, so the
    // sampled direction comes from the field reading itself. Every compass is reported in body
    // frame, which is the frame the autopilot bins the samples in, so the primary one stands for
    // all of them.
    field_direction(): { x: number, y: number, z: number } {
      const raw_imu = mavlink_store_get(mavlink, 'RAW_IMU.messageData.message') as Dictionary<number> | null
      return { x: raw_imu?.xmag ?? 0, y: raw_imu?.ymag ?? 0, z: raw_imu?.zmag ?? 0 }
    },
    // Roll and pitch come from the accelerometers, but heading comes from the compass being
    // calibrated, so the vehicle can be drawn pointing the wrong way. The grid turns with it either
    // way, so which section is lit stays right regardless.
    attitude(): { roll: number, pitch: number, yaw: number } {
      const attitude = mavlink_store_get(mavlink, 'ATTITUDE.messageData.message') as Dictionary<number> | null
      return { roll: attitude?.roll ?? 0, pitch: attitude?.pitch ?? 0, yaw: attitude?.yaw ?? 0 }
    },
  },
  watch: {
    all_compasses_calibrated(newValue) {
      if (newValue) {
        this.calibrationFinished()
      }
    },
    dialog(newValue) {
      if (!newValue) {
        this.dismiss()
      }
    },
  },
  beforeMount() {
    this.state = states.IDLE
    this.fitness = {}
    this.cleanup()
  },
  beforeDestroy() {
    this.progress_listener?.discard()
    this.unsubscribeField()
  },
  methods: {
    reset() {
      this.state = states.IDLE
      this.cleanup()
      this.fitness = {}
    },
    dismiss() {
      this.state = states.IDLE
      this.dialog = false
      this.cleanup()
      this.fitness = {}
    },
    subscribeField() {
      if (this.field_subscribed) {
        return
      }
      for (const messageName of GRID_MESSAGES) {
        mavlink.subscribeMessageRefreshRate({ messageName, refreshRate: GRID_REFRESH_RATE })
      }
      this.field_subscribed = true
    },
    unsubscribeField() {
      if (!this.field_subscribed) {
        return
      }
      for (const messageName of GRID_MESSAGES) {
        mavlink.unsubscribeMessageRefreshRate({ messageName, refreshRate: GRID_REFRESH_RATE })
      }
      this.field_subscribed = false
    },
    cleanup() {
      this.progress_listener?.discard()
      this.report_listener?.discard()
      this.unsubscribeField()
      this.percent = 0
      this.completion_mask = []
      this.progress_compass_id = undefined
      this.status_type = undefined
      this.status_text = undefined
    },
    calibrationFinished() {
      this.status_type = 'success'
      this.status_text = 'Calibration finished'
      this.state = states.DONE
      autopilot_data.setRebootRequired(true)
      this.cleanup()
    },
    calibrationFailed(reason: string) {
      this.status_text = `Calibration failed: ${reason}`
      this.status_type = 'error'
      this.state = states.FAILED
    },
    async cancelCalibration() {
      mavlink2rest.sendCommandLong(MavCmd.MAV_CMD_DO_CANCEL_MAG_CAL)
      const ack = await mavlink2rest.waitForAck(MavCmd.MAV_CMD_DO_CANCEL_MAG_CAL)
      if (ack.result.type !== MavResult.MAV_RESULT_ACCEPTED) {
        throw new Error(`Unexpected response trying to cancel calibration: ${ack.result.type}`)
      }
      this.percent = 0
      this.status_text = 'Calibration cancelled'
      this.status_type = 'warning'
      this.progress_listener?.discard()
      this.state = states.FAILED
    },
    async calibrate() {
      this.fitness = {}
      this.status_text = undefined
      this.state = states.CALIBRATING
      this.subscribeField()
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_DO_START_MAG_CAL,
        this.compass_mask,
        0,
        1, // auto-save calibration
      )
      try {
        const ack = await mavlink2rest.waitForAck(MavCmd.MAV_CMD_DO_START_MAG_CAL)
        if (ack.result.type !== MavResult.MAV_RESULT_ACCEPTED) {
          throw new Error(`Unexpected response: ${ack.result.type}`)
        }
        this.progress_listener = mavlink2rest.startListening(MAVLinkType.MAG_CAL_PROGRESS).setCallback(
          (message) => {
            this.percent = Math.max(message.message.completion_pct, 0.01)
            // Each calibrating compass sends its own progress, follow a single one so the grid doesn't
            // flip between masks that are slightly out of step with each other
            if (this.progress_compass_id === undefined) {
              this.progress_compass_id = message.message.compass_id
            }
            if (message.message.compass_id !== this.progress_compass_id) {
              return
            }
            this.completion_mask = message.message.completion_mask
          },
        ).setFrequency(0)
        this.report_listener = mavlink2rest.startListening(MAVLinkType.MAG_CAL_REPORT).setCallback(
          (message) => {
            const name = this.compasses[message.message.compass_id].deviceName ?? 'unknown'
            // we need to use Vue.set when adding a key to a dict to ensure reactivity...
            Vue.set(this.fitness, name, message.message.fitness)
          },
        ).setFrequency(0)
      } catch (error) {
        this.calibrationFailed(`${error}`)
      }
    },

  },
}
</script>
