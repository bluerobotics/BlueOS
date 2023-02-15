<template>
  <v-container fluid>
    <v-tabs
      v-model="tab"
      fixed-tabs
    >
      <v-tab>
        <v-icon class="mr-5">
          mdi-bookshelf
        </v-icon>
        Overview
      </v-tab>
      <v-tab>
        <v-icon class="mr-5">
          mdi-bookshelf
        </v-icon>
        PWM Outputs
      </v-tab>
    </v-tabs>
    <pwm-setup
      v-if="tab === 1"
    />
    <setup-overview v-if="tab === 0" />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import { fetchFirmwareVehicleType, fetchVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import PwmSetup from '@/components/vehiclesetup/PwmSetup.vue'
import setupOverview from '@/components/vehiclesetup/SetupOverview.vue'
import { callPeriodically, stopCallingPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'VehicleSetupView',
  components: {
    PwmSetup,
    setupOverview,
  },
  data() {
    return {
      tab: 0,
    }
  },
  mounted() {
    callPeriodically(fetchVehicleType, 10000)
    callPeriodically(fetchFirmwareVehicleType, 10000)
  },
  beforeDestroy() {
    stopCallingPeriodically(fetchVehicleType)
    stopCallingPeriodically(fetchFirmwareVehicleType)
  },
})
</script>
