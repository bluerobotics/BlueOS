<template>
  <v-dialog
    v-model="dialog"
    width="600"
  >
    <template #activator="{ on, attrs }">
      <v-btn
        color="primary"
        class="start-btn"
        v-bind="attrs"
        v-on="on"
      >
        {{ t`Start Large Vehicle Calibration` }}
      </v-btn>
    </template>

    <v-card>
      <v-card-title class="text-h5 grey lighten-2 black--text">
        {{ t`Large Vehicle Compass Calibration` }}
      </v-card-title>
      <v-card-text>
        {{ t`A valid global region/position is required to estimate the local world magnetic field.` }}
        <auto-coordinate-detector
          v-model="coordinates"
        />
        <compass-mask-picker v-model="compass_mask" :devices="compasses" />
        <v-divider />
        <v-alert
          v-if="status_text"
          :type="status_type"
        >
          {{ status_text }}
        </v-alert>
        <StatusTextWatcher :style="`display : ${status_type === 'error' ? 'block' : 'none'};`" />
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn color="primary" :disabled="calibrating || !compass_mask || !coordinates" @click="calibrate()">
          {{ t`Calibrate` }}
        </v-btn>
        <reboot-button />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import StatusTextWatcher from '@/components/common/StatusTextWatcher.vue'
import RebootButton from '@/components/utils/RebootButton.vue'
import { deviceId } from '@/utils/deviceid_decoder'

import {
  CalibrationKind, CalibrationSession, CalibrationWatcher, isRunning, ResultAlert,
  resultAlert,
} from '../../calibration'

export default Vue.extend({
  name: 'LargeVehicleCompassCalibrator',
  components: {
    StatusTextWatcher,
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
      // A finished session only shows until the dialog closes, or not at all if it finished before page load
      dismissed: true,
      error: '',
      session: null as CalibrationSession | null,
      watcher: null as CalibrationWatcher | null,
    }
  },
  computed: {
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
      if (!open) {
        this.dismissed = true
        this.error = ''
      }
    },
  },
  mounted() {
    this.watcher = new CalibrationWatcher(CalibrationKind.LARGE_VEHICLE_COMPASS, this.onSession)
  },
  beforeDestroy() {
    this.watcher?.stop()
  },
  methods: {
    onSession(session: CalibrationSession) {
      if (isRunning(session)) {
        this.dismissed = false
      }
      this.session = session
    },
    async calibrate() {
      this.dismissed = false
      this.error = await this.watcher?.start({
        compass_mask: this.compass_mask,
        latitude: this.coordinates?.lat,
        longitude: this.coordinates?.lon,
      }) ?? ''
    },
  },
})
</script>
<style scoped>
/* This label is the longest of the calibration buttons and a button never
   shrinks below its text, so let it wrap instead of outgrowing the card */
.start-btn {
  max-width: 100%;
  height: auto;
  min-height: 36px;
  padding: 6px 16px;
}

.start-btn ::v-deep .v-btn__content {
  white-space: normal;
  flex: 1 1 auto;
}
</style>
