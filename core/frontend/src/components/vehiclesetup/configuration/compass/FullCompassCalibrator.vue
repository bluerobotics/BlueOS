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
        </span>

        <auto-coordinate-detector
          v-if="state === states.IDLE"
          warnonly
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
import { Dictionary } from '@/types/common'
import { deviceId } from '@/utils/deviceid_decoder'

import CalibrationQualityIndicator from './CalibrationQualityIndicator.vue'

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
      compass_mask: 0,
      status_type: '' as string | undefined,
      status_text: '' as string | undefined,
      percent: 0,
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
    cleanup() {
      this.progress_listener?.discard()
      this.report_listener?.discard()
      this.percent = 0
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
