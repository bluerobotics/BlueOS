<template>
  <div v-if="params_finished_loaded" class="pt-1 pb-1">
    <div class="ma-3 pa-1 d-flex flex-row flex-wrap flex-grow-0 justify-center failsafes-container">
      <failsafe-card
        v-for="failsafeDefinition in failsafes"
        :key="failsafeDefinition.name"
        :failsafe-definition="failsafeDefinition"
      />
    </div>
  </div>
</template>

<script lang="ts">
import { t } from 'ttag'

import failsafeCard from '@/components/vehiclesetup/configuration/failsafes/FailsafeCard.vue'
import autopilot_data from '@/store/autopilot'

import { FailsafeDefinition } from './types'

export default {
  name: 'FailsafesConfiguration',
  components: {
    failsafeCard,
  },
  data() {
    return {
      failsafes: [] as FailsafeDefinition[],
    }
  },
  computed: {
    params_finished_loaded(): boolean {
      return autopilot_data.finished_loading
    },
  },
  mounted() {
    // we fetch the failsafes on mounting because we
    // need to be in an async context to wait for the import calls
    this.get_failsafes().then((failsafes) => {
      this.failsafes = failsafes
    })
  },
  methods: {
    async get_failsafes(): Promise<FailsafeDefinition[]> {
      const failsafes: FailsafeDefinition[] = [
        {
          name: 'Control Station Heartbeat Loss',
          generalDescription: t`Triggers when the vehicle does not receive a heartbeat from the GCS within the timeout (default 3 seconds).`, // eslint-disable-line max-len
          image: (await import('@/assets/img/configuration/failsafes/heartbeat.svg')).default as string,

          params: [
            {
              replacementTitle: 'Timeout',
              icon: 'mdi-timer',
              name: 'FS_GCS_TIMEOUT',
              optional: true,
            },
            {
              replacementTitle: 'Enable',
              icon: 'mdi-toggle-switch',
              name: 'FS_GCS_ENABLE',
              replacementDescription: '',
            },
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_ACTION',
              replacementDescription: '',
              optional: true,
            },
          ],
        },
        {
          name: 'Pilot Input Loss',
          generalDescription: t`Triggers when the vehicle does not receive any pilot input for a given amount of time.`,
          image: (await import('@/assets/img/configuration/failsafes/pilot-input.svg')).default as string,
          params: [
            {
              replacementTitle: 'Timeout',
              icon: 'mdi-timer-outline',
              name: 'FS_PILOT_TIMEOUT',
            },
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_PILOT_INPUT',
            },
          ],
        },
        {
          // TODO: move actual pin configuration to its own setup page
          name: 'Leak Detection',
          generalDescription: t`Triggers when a leak is detected. We recommend keeping control electronics dry.`,
          image: (await import('@/assets/img/configuration/failsafes/leak.svg')).default as string,
          params: [
            {
              replacementTitle: 'Leak probe 1 type',
              name: 'LEAK1_TYPE',
              optional: true,
            },
            {
              replacementTitle: 'Leak 1 pin',
              icon: 'mdi-pin',
              name: 'LEAK1_PIN',
            },
            {
              replacementTitle: 'Leak 1 logic level when dry',
              name: 'LEAK1_LOGIC',
            },
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_LEAK_ENABLE',
            },
          ],
        },
        {
          name: 'Low Battery',
          generalDescription: t`Triggers when the voltage goes below specified thresholds. This can help to avoid damage to the battery and potentially loss of the vehicle.`, // eslint-disable-line max-len
          image: (await import('@/assets/img/configuration/failsafes/battery.svg')).default as string,
          params: [
            // TODO: add support for the MAH params and coloumb counting
            {
              replacementTitle: 'Voltage measurement source',
              icon: 'mdi-source-branch',
              name: 'BATT_FS_VOLTSRC',
            },
            {
              replacementTitle: 'Low voltage threshold',
              icon: 'mdi-battery-30',
              name: 'BATT_LOW_VOLT',
            },
            {
              replacementTitle: 'Low voltage timeout',
              icon: 'mdi-timer-outline',
              name: 'BATT_LOW_TIMER',
            },
            {
              replacementTitle: 'Action when battery is low',
              icon: 'mdi-lightning-bolt',
              name: 'BATT_FS_LOW_ACT',
            },
            {
              replacementTitle: 'Critical voltage threshold',
              icon: 'mdi-battery-alert-variant-outline',
              name: 'BATT_CRT_VOLT',
            },
            {
              replacementTitle: 'Action when battery is critical',
              icon: 'mdi-skull-crossbones-outline',
              name: 'BATT_FS_CRT_ACT',
            },
          ],
        },
        {
          name: 'Excess Internal Pressure',
          generalDescription: t`Triggers when the internal pressure is too high. This may help to detect a leak, and to avoid rapid unplanned disassembly.`, // eslint-disable-line max-len
          image: (await import('@/assets/img/configuration/failsafes/pressure.svg')).default as string,
          params: [

            {
              replacementTitle: 'Maximum internal pressure',
              icon: 'mdi-gauge-full',
              name: 'FS_PRESS_MAX',
            },
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_PRESS_ENABLE',
            },
          ],
        },
        {
          name: 'Excess Internal Temperature',
          generalDescription: t`Triggers when the internal temperature is too high. This may help to prevent damage to electronics due to overheating.`, // eslint-disable-line max-len
          image: (await import('@/assets/img/configuration/failsafes/temperature.svg')).default as string,
          params: [

            {
              replacementTitle: 'Maximum internal temperature',
              icon: 'mdi-thermometer-high',
              name: 'FS_TEMP_MAX',
            },
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_TEMP_ENABLE',
            },
          ],
        },
        {
          name: 'Sensor Fusion Uncertainty',
          generalDescription: t`Triggers when the EKF variances surpass a given threshold, so it loses trust in its state estimates.`, // eslint-disable-line max-len
          image: (await import('@/assets/img/configuration/failsafes/ekf.svg')).default as string,
          params: [
            {
              replacementTitle: 'Variance threshold',
              icon: 'mdi-chart-bell-curve',
              name: 'FS_EKF_THRESH',
            },
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_EKF_ACTION',
            },
          ],
        },
        {
          name: 'Crash Detection',
          generalDescription: t`Triggers when a crash has occurred.`,
          image: (await import('@/assets/img/configuration/failsafes/crash.svg')).default as string,
          params: [
            {
              replacementTitle: 'Action',
              icon: 'mdi-lightning-bolt',
              name: 'FS_CRASH_CHECK',
            },
          ],
        },
      ]
      return failsafes
    },
  },
}
</script>
<style scoped>
.main-container {
  display: flex;
  column-gap: 10px;
  padding: 10px;
}

.failsafes-container {
  gap: 8px;
}
</style>
