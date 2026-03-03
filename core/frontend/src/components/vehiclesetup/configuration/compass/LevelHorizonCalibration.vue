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
        Level Horizon
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5">
        Accelerometer Calibration
      </v-card-title>
      <v-card-text>
        <div>
          Horizon calibration trims the pitch and roll of the vehicle's
          inertial sensors to adjust for small deviations from level.
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
            <span>Roll: {{ rollDeg.toFixed(1) }}°</span>
            <span>Pitch: {{ pitchDeg.toFixed(1) }}°</span>
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
          Calibrate
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd, MavResult } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import autopilot_data from '@/store/autopilot'
import mavlink from '@/store/mavlink'
import { Dictionary } from '@/types/common'
import mavlink_store_get from '@/utils/mavlink'

const RAD_TO_DEG = 180 / Math.PI
const PITCH_SCALE = 2

export default Vue.extend({
  name: 'LevelHorizonCalibration',
  data() {
    return {
      dialog: false,
      calibrating: false,
      status_type: undefined as string | undefined,
      status_text: undefined as string | undefined,
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
  },
  watch: {
    dialog(open: boolean) {
      if (open) {
        mavlink.setMessageRefreshRate({ messageName: 'ATTITUDE', refreshRate: 10 })
      } else {
        this.status_text = undefined
        this.status_type = undefined
      }
    },
  },
  methods: {
    calibrationFinished() {
      this.status_type = 'success'
      this.status_text = 'Calibration finished'
      this.calibrating = false
      autopilot_data.setRebootRequired(true)
    },
    calibrationFailed(error: string) {
      this.status_text = `Calibration failed: ${error}`
      this.status_type = 'error'
      this.calibrating = false
    },
    async calibrate() {
      this.status_text = undefined
      this.status_type = undefined
      this.calibrating = true
      this.levelHorizon()
      try {
        const ack = await mavlink2rest.waitForAck(MavCmd.MAV_CMD_PREFLIGHT_CALIBRATION)
        if (ack.result.type !== MavResult.MAV_RESULT_ACCEPTED) {
          throw new Error(`Unexpected result: ${ack.result.type}`)
        }
        this.calibrationFinished()
      } catch (error) {
        this.calibrationFailed(`${error}`)
      }
    },
    levelHorizon() {
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_PREFLIGHT_CALIBRATION,
        0,
        0,
        0,
        0,
        2, // Level Horizon
        0,
        0,
      )
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
