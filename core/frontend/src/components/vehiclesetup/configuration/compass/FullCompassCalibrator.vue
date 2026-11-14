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
        {{ t`Start Full Calibration` }}
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5 grey lighten-2 black--text">
        {{ t`Onboard Compass Calibration` }}
      </v-card-title>
      <v-card-text class="pa-10">
        <span v-if="state === states.IDLE">
          <p>
            <!-- eslint-disable-next-line vue/no-v-html, max-len -->
            <span v-html="t`<strong>Onboard Compass Calibration</strong> is the regular calibration used for ArduPilot vehicles. It requires spinning the vehicle around all axes, which allows it to calibrate the readings to the expected local magnetic field.`" />
          </p>
          <p>
            <!-- eslint-disable-next-line vue/no-v-html, max-len -->
            <span v-html="t`A valid global region/position is <strong>recomended</strong> for Onboard Calibration to estimate the local world magnetic field.`" />
          </p>
        </span>
        <span v-else-if="state === states.CALIBRATING">
          {{ t`Spin your vehicle around all of its axes until the progress bar completes.` }}
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
            <th>{{ t`Compass` }}</th>
            <th>
              {{ t`Fitness (mGauss)` }}
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
          v-if="state === states.CALIBRATING"
          :value="percent"
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
          {{ t`Calibrate` }}
        </v-btn>
        <v-btn v-if="state === states.DONE" color="primary" @click="dismiss">
          {{ t`Dismiss` }}
        </v-btn>
        <RebootButton />
        <v-btn v-if="state == states.CALIBRATING" color="red" @click="cancelCalibration()">
          {{ t`Cancel` }}
        </v-btn>
        <v-btn v-if="state == states.FAILED" color="primary" @click="reset()">
          {{ t`Ok` }}
        </v-btn>
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import RebootButton from '@/components/utils/RebootButton.vue'
import { Dictionary } from '@/types/common'
import { deviceId } from '@/utils/deviceid_decoder'

import {
  CalibrationKind, CalibrationSession, CalibrationStatus, CalibrationWatcher, isRunning, ResultAlert,
  resultAlert,
} from '../../calibration'
import CalibrationQualityIndicator from './CalibrationQualityIndicator.vue'

enum states {
  IDLE,
  CALIBRATING,
  DONE,
  FAILED,
}

export default Vue.extend({
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
      // A finished session only shows until the user dismisses it, or not at all if it finished before page load
      dismissed: true,
      error: '',
      session: null as CalibrationSession | null,
      watcher: null as CalibrationWatcher | null,
    }
  },
  computed: {
    states() {
      return states
    },
    state(): states {
      const { error, session } = this
      if (error && !isRunning(session)) {
        return states.FAILED
      }
      if (session === null || this.dismissed && !isRunning(session)) {
        return states.IDLE
      }
      switch (session.status) {
        case CalibrationStatus.DONE:
          return states.DONE
        case CalibrationStatus.FAILED:
        case CalibrationStatus.CANCELLED:
          return states.FAILED
        default:
          return states.CALIBRATING
      }
    },
    percent(): number {
      return this.session?.progress ?? 0
    },
    fitness(): Dictionary<number> {
      if (this.state === states.IDLE) {
        return {}
      }
      return Object.fromEntries(Object.entries(this.session?.fitness ?? {}).map(
        ([compass_id, fit]) => [this.compasses[Number(compass_id)]?.deviceName ?? 'unknown', fit],
      ))
    },
    result(): ResultAlert | undefined {
      return this.state === states.IDLE ? undefined : resultAlert(this.session, this.error)
    },
    status_text(): string | undefined {
      return this.result?.text
    },
    status_type(): string | undefined {
      return this.result?.type
    },
  },
  watch: {
    dialog(newValue: boolean) {
      if (!newValue) {
        this.dismiss()
      }
    },
  },
  mounted() {
    this.watcher = new CalibrationWatcher(CalibrationKind.COMPASS, this.onSession)
  },
  beforeDestroy() {
    this.watcher?.stop()
  },
  methods: {
    onSession(session: CalibrationSession) {
      if (isRunning(session)) {
        // Resume a calibration started before a page reload
        if (this.session === null) {
          this.dialog = true
        }
        this.dismissed = false
      }
      this.session = session
    },
    reset() {
      this.dismissed = true
      this.error = ''
    },
    dismiss() {
      this.dialog = false
      if (isRunning(this.session)) {
        this.cancelCalibration()
      }
      this.reset()
    },
    async cancelCalibration() {
      this.error = await this.watcher?.cancel() ?? ''
    },
    async calibrate() {
      this.error = await this.watcher?.start({
        compass_mask: this.compass_mask,
      }) ?? ''
    },
  },
})
</script>
