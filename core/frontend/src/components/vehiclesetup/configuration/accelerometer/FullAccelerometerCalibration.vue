<template>
  <v-dialog
    v-model="dialog"
    :persistent="!show_ok_button && !show_next_button && !show_start_button"
    width="500"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        class="ma-2"
        v-bind="attrs"
        v-on="on"
      >
        {{ t`Start Full Calibration` }}
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5">
        {{ t`Accelerometer Calibration` }}
      </v-card-title>
      <div class="ma-6">
        <p>
          <!-- eslint-disable-next-line max-len -->
          {{ t`Full accelerometer calibration requires you to place the vehicle onto all of its sides and keep it still for a few seconds. This will allow the autopilot to calibrate the accelerometer.` }}
        </p>
      </div>
      <v-alert
        v-if="![states.IDLE, states.WAITING_FOR_VEHICLE_RESPONSE].includes(state)"
        dense
        :type="current_state_type"
      >
        <strong>{{ current_state_text }}</strong>
      </v-alert>
      <v-alert v-if="error" dense type="error">
        {{ error }}
      </v-alert>
      <generic-viewer
        :autorotate="false"
        :transparent="false"
        :cameracontrols="false"
        :orientation="current_state_3D"
        :style="{ height: '320px' }"
      />
      <v-card-actions class="justify-center">
        <v-btn v-if="show_start_button" :loading="start_button_loading" class="primary" @click="startCalibration">
          {{ t`Start Calibration` }}
        </v-btn>
        <v-btn v-if="show_next_button" :loading="next_button_loading" class="primary" @click="nextStep">
          {{ t`Next` }}
        </v-btn>
        <v-btn v-if="show_ok_button" class="primary" @click="cleanup">
          {{ t`Ok` }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import GenericViewer from '@/components/vehiclesetup/viewers/GenericViewer.vue'

import {
  CalibrationKind, CalibrationSession, CalibrationStatus, CalibrationWatcher, isRunning, PoseKey,
} from '../../calibration'

enum CalState {
  IDLE,
  WAITING_FOR_VEHICLE_RESPONSE,
  WAITING_FOR_LEVEL_POSITION,
  WAITING_FOR_LEFT_POSITION,
  WAITING_FOR_RIGHT_POSITION,
  WAITING_FOR_NOSEDOWN_POSITION,
  WAITING_FOR_NOSEUP_POSITION,
  WAITING_FOR_BACK_POSITION,
  SUCCESS,
  FAIL,
}

const POSITION_STATES: Record<PoseKey, CalState> = {
  [PoseKey.LEVEL]: CalState.WAITING_FOR_LEVEL_POSITION,
  [PoseKey.LEFT]: CalState.WAITING_FOR_LEFT_POSITION,
  [PoseKey.RIGHT]: CalState.WAITING_FOR_RIGHT_POSITION,
  [PoseKey.NOSE_DOWN]: CalState.WAITING_FOR_NOSEDOWN_POSITION,
  [PoseKey.NOSE_UP]: CalState.WAITING_FOR_NOSEUP_POSITION,
  [PoseKey.BACK]: CalState.WAITING_FOR_BACK_POSITION,
}

export default Vue.extend({
  name: 'FullAccelerometerCalibration',
  components: {
    GenericViewer,
  },
  data() {
    return {
      dialog: false,
      // A finished session only shows until the user dismisses it, or not at all if it finished before page load
      dismissed: true,
      error: '',
      reset_timeout: undefined as ReturnType<typeof setTimeout> | undefined,
      session: null as CalibrationSession | null,
      watcher: null as CalibrationWatcher | null,
    }
  },
  computed: {
    states() {
      return CalState
    },
    state(): CalState {
      const { session } = this
      if (session === null || this.dismissed && !isRunning(session)) {
        return CalState.IDLE
      }
      switch (session.status) {
        case CalibrationStatus.DONE:
          return CalState.SUCCESS
        case CalibrationStatus.FAILED:
        case CalibrationStatus.CANCELLED:
          return CalState.FAIL
        default:
          return session.position ? POSITION_STATES[session.position] : CalState.WAITING_FOR_VEHICLE_RESPONSE
      }
    },
    show_next_button(): boolean {
      return ![
        CalState.IDLE,
        CalState.FAIL,
        CalState.SUCCESS,
        CalState.WAITING_FOR_VEHICLE_RESPONSE,
      ].includes(this.state)
    },
    next_button_loading(): boolean {
      return this.session?.status === CalibrationStatus.RUNNING
    },
    show_ok_button(): boolean {
      return [CalState.SUCCESS, CalState.FAIL].includes(this.state)
    },
    show_start_button(): boolean {
      return [CalState.IDLE, CalState.WAITING_FOR_VEHICLE_RESPONSE].includes(this.state)
    },
    start_button_loading(): boolean {
      return this.state === CalState.WAITING_FOR_VEHICLE_RESPONSE
    },
    current_state_text(): string {
      const AccelStateText: { [key: number]: string } = {
        [CalState.WAITING_FOR_LEVEL_POSITION]: 'Place the vehicle on a level surface',
        [CalState.WAITING_FOR_LEFT_POSITION]: 'Place the vehicle on its left side',
        [CalState.WAITING_FOR_RIGHT_POSITION]: 'Place the vehicle on its right side',
        [CalState.WAITING_FOR_NOSEDOWN_POSITION]: 'Place the vehicle with its nose down',
        [CalState.WAITING_FOR_NOSEUP_POSITION]: 'Place the vehicle with its nose up',
        [CalState.WAITING_FOR_BACK_POSITION]: 'Place the vehicle on its back',
        [CalState.SUCCESS]: 'Calibration Successful',
        [CalState.FAIL]: this.session?.status === CalibrationStatus.CANCELLED
          ? 'Calibration Cancelled' : 'Calibration Failed',
      }
      const text = AccelStateText[Number(this.state)] ?? 'Unknown state'
      return this.session?.reason ? `${text}: ${this.session.reason}` : text
    },
    current_state_3D(): string {
      const AccelStateText: { [key: number]: string } = {
        [CalState.WAITING_FOR_LEVEL_POSITION]: '0deg 0deg 0deg',
        [CalState.WAITING_FOR_LEFT_POSITION]: '-90deg 0deg 0deg',
        [CalState.WAITING_FOR_RIGHT_POSITION]: '90deg 0deg 0deg',
        [CalState.WAITING_FOR_NOSEDOWN_POSITION]: '0deg 90deg 0deg',
        [CalState.WAITING_FOR_NOSEUP_POSITION]: '0deg -90deg 0deg',
        [CalState.WAITING_FOR_BACK_POSITION]: '0deg 180deg 0deg',
      }
      return AccelStateText[Number(this.state)] ?? '0deg 0deg 0deg'
    },
    current_state_type(): string {
      if (this.state === CalState.SUCCESS) {
        return 'success'
      }
      if (this.state === CalState.FAIL) {
        return 'error'
      }
      return 'info'
    },
  },
  watch: {
    dialog(open: boolean) {
      if (!open && isRunning(this.session)) {
        this.cancel()
      }
    },
  },
  mounted() {
    this.watcher = new CalibrationWatcher(CalibrationKind.ACCELEROMETER, this.onSession)
  },
  beforeDestroy() {
    clearTimeout(this.reset_timeout)
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
      const succeeded = session.status === CalibrationStatus.DONE && isRunning(this.session)
      this.session = session
      if (succeeded) {
        this.cleanup()
      }
    },
    async nextStep() {
      this.error = await this.watcher?.confirm() ?? ''
    },
    async cancel() {
      this.error = await this.watcher?.cancel() ?? ''
    },
    cleanup() {
      this.dialog = false
      // delay resetting the state to wait for the close animation to finish
      this.reset_timeout = setTimeout(() => { this.dismissed = true }, 500)
    },
    async startCalibration() {
      this.error = await this.watcher?.start() ?? ''
    },
  },
})
</script>
