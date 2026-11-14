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
        {{ t`Level Horizon` }}
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5">
        {{ t`Accelerometer Calibration` }}
      </v-card-title>
      <v-card-text>
        <div>
          <!-- eslint-disable-next-line max-len -->
          {{ t`Horizon calibration trims the pitch and roll of the vehicle's inertial sensors to adjust for small deviations from level.` }}
        </div>
        <div class="attitude-container mt-4">
          <svg
            viewBox="-120 -120 240 240"
            class="attitude-indicator"
          >
            <defs>
              <clipPath id="horizon-clip">
                <circle r="100" />
              </clipPath>
            </defs>
            <g clip-path="url(#horizon-clip)">
              <g :transform="`rotate(${rollDeg}) translate(0, ${pitchOffset})`">
                <rect x="-150" y="-150" width="300" height="150" fill="#3a8fd6" />
                <rect x="-150" y="0" width="300" height="150" fill="#6b4a2a" />
                <line x1="-150" y1="0" x2="150" y2="0" stroke="white" stroke-width="1.5" />
                <line
                  v-for="tick in pitchTicks"
                  :key="`tick-${tick}`"
                  :x1="tick === 0 ? -30 : -15"
                  :y1="-tick * pitchScale"
                  :x2="tick === 0 ? 30 : 15"
                  :y2="-tick * pitchScale"
                  stroke="white"
                  stroke-width="0.8"
                  opacity="0.7"
                />
              </g>
            </g>
            <circle r="100" fill="none" stroke="#333" stroke-width="3" />
            <!-- Fixed aircraft reference -->
            <line x1="-35" y1="0" x2="-10" y2="0" stroke="#ffa000" stroke-width="3" stroke-linecap="round" />
            <line x1="10" y1="0" x2="35" y2="0" stroke="#ffa000" stroke-width="3" stroke-linecap="round" />
            <circle r="4" fill="none" stroke="#ffa000" stroke-width="2.5" />
          </svg>
          <div class="attitude-readout">
            <span>{{ t`Roll: ${rollDeg.toFixed(1)}°` }}</span>
            <span>{{ t`Pitch: ${pitchDeg.toFixed(1)}°` }}</span>
          </div>
        </div>
        <v-alert
          v-if="status_text"
          :type="status_type"
          class="mt-2"
        >
          {{ status_text }}
        </v-alert>
        <status-text-watcher :style="`display : ${status_type === 'error' ? 'block' : 'none'};`" />
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn color="primary" :disabled="calibrating" @click="calibrate()">
          {{ t`Calibrate` }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink from '@/store/mavlink'
import { Dictionary } from '@/types/common'
import mavlink_store_get from '@/utils/mavlink'

import {
  CalibrationKind, CalibrationSession, CalibrationWatcher, isRunning, ResultAlert,
  resultAlert,
} from '../../calibration'

const RAD_TO_DEG = 180 / Math.PI
const PITCH_SCALE = 2

export default Vue.extend({
  name: 'LevelHorizonCalibration',
  data() {
    return {
      dialog: false,
      attitude_subscribed: false,
      // A finished session only shows until the dialog closes, or not at all if it finished before page load
      dismissed: true,
      error: '',
      session: null as CalibrationSession | null,
      watcher: null as CalibrationWatcher | null,
      pitchTicks: [-20, -10, 0, 10, 20],
      pitchScale: PITCH_SCALE,
    }
  },
  computed: {
    attitude(): Dictionary<number> | null {
      return mavlink_store_get(mavlink, 'ATTITUDE.messageData.message') as Dictionary<number> | null
    },
    rollDeg(): number {
      return -(this.attitude?.roll ?? 0) * RAD_TO_DEG
    },
    pitchDeg(): number {
      return (this.attitude?.pitch ?? 0) * RAD_TO_DEG
    },
    pitchOffset(): number {
      return this.pitchDeg * PITCH_SCALE
    },
    calibrating(): boolean {
      return isRunning(this.session)
    },
    result(): ResultAlert | undefined {
      return this.dismissed ? undefined : resultAlert(this.session, this.error)
    },
    status_text(): string | undefined {
      return this.result?.text
    },
    status_type(): string | undefined {
      return this.result?.type
    },
  },
  watch: {
    dialog(open: boolean) {
      if (open) {
        this.subscribeAttitude()
      } else {
        this.unsubscribeAttitude()
        this.dismissed = true
        this.error = ''
      }
    },
  },
  mounted() {
    this.watcher = new CalibrationWatcher(CalibrationKind.BOARD_LEVEL, this.onSession)
  },
  beforeDestroy() {
    this.unsubscribeAttitude()
    this.watcher?.stop()
  },
  methods: {
    subscribeAttitude() {
      if (this.attitude_subscribed) {
        return
      }
      mavlink.subscribeMessageRefreshRate({ messageName: 'ATTITUDE', refreshRate: 10 })
      this.attitude_subscribed = true
    },
    unsubscribeAttitude() {
      if (!this.attitude_subscribed) {
        return
      }
      mavlink.unsubscribeMessageRefreshRate({ messageName: 'ATTITUDE', refreshRate: 10 })
      this.attitude_subscribed = false
    },
    onSession(session: CalibrationSession) {
      if (isRunning(session)) {
        this.dismissed = false
      }
      this.session = session
    },
    async calibrate() {
      this.dismissed = false
      this.error = await this.watcher?.start() ?? ''
    },
  },
})
</script>

<style scoped>
.attitude-container {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.attitude-indicator {
  width: 200px;
  height: 200px;
}

.attitude-readout {
  display: flex;
  gap: 24px;
  margin-top: 8px;
  font-family: monospace;
  font-size: 14px;
  opacity: 0.8;
}
</style>
