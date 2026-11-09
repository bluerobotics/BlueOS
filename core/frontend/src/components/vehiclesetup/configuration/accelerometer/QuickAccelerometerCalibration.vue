<template>
  <v-dialog
    v-model="dialog"
    width="500"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        class="ma-2"
        v-bind="attrs"
        v-on="on"
      >
        {{ t`Quick Calibration` }}
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5">
        {{ t`Accelerometer Calibration` }}
      </v-card-title>
      <v-card-text>
        <div>
          <!-- eslint-disable-next-line max-len -->
          {{ t`Quick calibration requires that you place the vehicle on a level surface and keep it still for a few seconds. It is usually enough if your vehicle is generally leveled while in use.` }}
        </div>
      </v-card-text>
      <v-card-text v-if="failure">
        <v-alert dense type="error">
          {{ failure }}
        </v-alert>
      </v-card-text>
      <v-card-actions>
        <v-alert v-if="state === states.CALIBRATED" type="success">
          {{ t`Calibration Successful` }}
        </v-alert>
        <v-btn v-if="state === states.IDLE" class="primary" @click="doCalibration">
          {{ t`Start Calibration` }}
        </v-btn>
        <SpinningLogo v-if="state === states.CALIBRATION_STARTED" size="15%" />
        <v-spacer />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'

import {
  CalibrationKind, CalibrationSession, CalibrationStatus, CalibrationWatcher, isRunning, statusText,
} from '../../calibration'

const states = {
  IDLE: 0,
  CALIBRATION_STARTED: 2,
  CALIBRATED: 3,
}

export default Vue.extend({
  name: 'QuickAccelerometerCalibration',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      dialog: false,
      // A finished session only shows until the dialog closes, or not at all if it finished before page load
      dismissed: true,
      error: '',
      close_timeout: undefined as ReturnType<typeof setTimeout> | undefined,
      session: null as CalibrationSession | null,
      watcher: null as CalibrationWatcher | null,
    }
  },
  computed: {
    states() {
      return states
    },
    state(): number {
      if (isRunning(this.session)) {
        return states.CALIBRATION_STARTED
      }
      if (!this.dismissed && this.session?.status === CalibrationStatus.DONE) {
        return states.CALIBRATED
      }
      return states.IDLE
    },
    failure(): string {
      if (this.error) {
        return this.error
      }
      return !this.dismissed && this.session?.status === CalibrationStatus.FAILED ? statusText(this.session) : ''
    },
  },
  watch: {
    dialog(open: boolean) {
      if (!open) {
        this.dismissed = true
        this.error = ''
      }
    },
  },
  mounted() {
    this.watcher = new CalibrationWatcher(CalibrationKind.SIMPLE_ACCELEROMETER, this.onSession)
  },
  beforeDestroy() {
    clearTimeout(this.close_timeout)
    this.watcher?.stop()
  },
  methods: {
    onSession(session: CalibrationSession) {
      if (isRunning(session)) {
        this.dismissed = false
      }
      const succeeded = session.status === CalibrationStatus.DONE && isRunning(this.session)
      this.session = session
      if (succeeded) {
        this.close_timeout = setTimeout(() => { this.dialog = false }, 2000)
      }
    },
    async doCalibration() {
      this.error = await this.watcher?.start() ?? ''
    },
  },
})
</script>
