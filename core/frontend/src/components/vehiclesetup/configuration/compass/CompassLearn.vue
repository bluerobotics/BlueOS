<template>
  <v-dialog
    v-model="dialog"
    width="500"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        :disabled="!learn_param || !is_supported.result"
        v-bind="attrs"
        v-on="on"
      >
        Start Compass Learn
      </v-btn>
      <span v-if="!is_supported.result" class="ml-2" style="color: red;">
        {{ is_supported.reason }}
      </span>
    </template>

    <v-card>
      <v-card-title class="text-h5 grey lighten-2 black--text">
        Compass Calibration Learning
      </v-card-title>
      <v-card-text>
        A valid global region is required for Compass Learn to estimate the local world magnetic field.
        <auto-coordinate-detector
          v-model="coordinates"
        />
        Make sure you have a valid region/position specified, then click start and drive the vehicle around
        in manual mode until you see the message <b>"CompassLearn: finished"</b>.
        <v-divider />
        <v-alert
          v-if="status_text"
          :type="status_type"
        >
          {{ status_text }}
        </v-alert>
        <status-text-watcher :filter="/CompassLearn:.*/" @message="onStatusMessage" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn v-if="!is_learning" color="primary" :disabled="calibrating || !coordinates" @click="start()">
          Start
        </v-btn>
        <v-btn v-else-if="is_learning" color="error" @click="stop()">
          Abort
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">

import StatusTextWatcher from '@/components/common/StatusTextWatcher.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter from '@/types/autopilot/parameter'

import AutoCoordinateDetector from './AutoCoordinateDetector.vue'

export default {
  name: 'CompassLearn',
  components: {
    StatusTextWatcher,
    AutoCoordinateDetector,
  },
  data() {
    return {
      dialog: false,
      coordinates: undefined as { lat: number, lon: number } | undefined,
      calibrating: false,
      status_type: '' as string | undefined,
      status_text: '' as string | undefined,
    }
  },
  computed: {
    learn_param(): Parameter | undefined {
      return autopilot_data.parameter('COMPASS_LEARN')
    },
    is_learning(): boolean {
      return this.learn_param?.value === 3
    },
    is_supported(): { result: boolean | string, reason?: string } {
      // Sub is the only vehicle supporting it with no GPS attached
      // and only between versions 4.1.2 to 4.5.0, for now.
      if (!autopilot.vehicle_type || !autopilot.firmware_info) {
        return { result: false, reason: 'Firmware not detected' }
      }
      if (autopilot.vehicle_type === 'Submarine'
        && (autopilot.firmware_info.version.compare('4.1.1') < 0
        || autopilot.firmware_info.version.compare('4.5.0') > 0)) {
        return {
          result: false,
          reason: `Unsupported firmware (${autopilot.firmware_info.version.raw}).`
           + 'Sub versions under 4.1.2 and over 4.5.0 require a GPS/DVL for Compass learning',
        }
      }
      return { result: true }
    },
  },
  methods: {
    onStatusMessage(message: string) {
      if (message.includes('CompassLearn: finished')) {
        this.calibrationFinished()
      } else if (message.includes('CompassLearn: failed')) {
        this.calibrationFailed()
      }
    },
    calibrationFinished() {
      this.status_type = 'success'
      this.status_text = 'Calibration finished'
      this.calibrating = false
    },
    calibrationFailed() {
      this.status_text = 'Calibration failed'
      this.status_type = 'error'
      this.calibrating = false
    },
    start() {
      if (this.learn_param === undefined) {
        console.error('learn_param is undefined')
        return
      }
      const COMPASS_LEARN_START = 3
      mavlink2rest.setParam(
        this.learn_param.name,
        COMPASS_LEARN_START,
        autopilot_data.system_id,
        this.learn_param.paramType.type,
      )
    },
    stop() {
      if (this.learn_param === undefined) {
        return
      }
      const COMPASS_LEARN_STOP = 0
      mavlink2rest.setParam(
        this.learn_param.name,
        COMPASS_LEARN_STOP,
        autopilot_data.system_id,
        this.learn_param.paramType.type,
      )
    },
  },
}
</script>
