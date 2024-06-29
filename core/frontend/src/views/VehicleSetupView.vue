<template>
  <v-container fluid>
    <v-tabs
      v-model="page_selected"
      centered
      icons-and-text
      show-arrows
    >
      <v-tabs-slider />
      <v-tab
        v-for="page in pages"
        :key="page.value"
      >
        {{ page.title }}
        <v-icon>{{ page.icon }}</v-icon>
      </v-tab>
    </v-tabs>
    <v-tabs-items v-model="page_selected">
      <v-tab-item
        v-for="page in pages"
        :key="page.value"
      >
        <parameter-loading-spinner>
          <pwm-setup v-if="page.value === 'pwm_outputs'" />
          <setup-overview v-else-if="page.value === 'overview'" />
          <configure v-else-if="page.value === 'configure'" />
        </parameter-loading-spinner>
      </v-tab-item>
    </v-tabs-items>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import { fetchFirmwareVehicleType, fetchVehicleType } from '@/components/autopilot/AutopilotManagerUpdater'
import ParameterLoadingSpinner from '@/components/utils/ParameterLoadingSpinner.vue'
import Configure from '@/components/vehiclesetup/Configure.vue'
import PwmSetup from '@/components/vehiclesetup/PwmSetup.vue'
import setupOverview from '@/components/vehiclesetup/SetupOverview.vue'
import { OneMoreTime } from '@/one-more-time'

export interface Item {
  title: string,
  icon: string,
  value: string,
}

export default Vue.extend({
  name: 'VehicleSetupView',
  components: {
    PwmSetup,
    setupOverview,
    Configure,
    ParameterLoadingSpinner,
  },
  data() {
    return {
      page_selected: null as string | null,
      pages: [
        { title: 'Overview', icon: 'mdi-view-dashboard-variant-outline', value: 'overview' },
        { title: 'PWM Outputs', icon: 'mdi-fan', value: 'pwm_outputs' },
        { title: 'Configure', icon: 'mdi-cog', value: 'configure' },
      ] as Item[],
      fetch_vehicle_type_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_firmware_vehicle_type_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  mounted() {
    this.fetch_vehicle_type_task.setAction(fetchVehicleType)
    this.fetch_firmware_vehicle_type_task.setAction(fetchFirmwareVehicleType)
  },
})
</script>
