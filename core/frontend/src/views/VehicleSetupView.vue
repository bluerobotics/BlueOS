<template>
  <v-container fluid>
    <v-tabs
      :value="currentTab"
      centered
      icons-and-text
      show-arrows
    >
      <v-tabs-slider />
      <v-tab
        v-for="page in pages"
        :key="page.value"
        :to="{ name: 'Vehicle Setup', params: { tab: page.value } }"
      >
        {{ page.title }}
        <v-icon>{{ page.icon }}</v-icon>
      </v-tab>
    </v-tabs>
    <v-tabs-items :value="currentTab">
      <v-tab-item
        v-for="page in pages"
        :key="page.value"
        :value="page.value"
      >
        <parameter-loading-spinner>
          <component :is="page.component" :subtab="$route.params.subtab" />
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
  component: unknown,
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
      pages: [
        {
          title: 'Overview', icon: 'mdi-view-dashboard-variant-outline', value: 'overview', component: setupOverview,
        },
        {
          title: 'PWM Outputs', icon: 'mdi-fan', value: 'pwm_outputs', component: PwmSetup,
        },
        {
          title: 'Configure', icon: 'mdi-cog', value: 'configure', component: Configure,
        },
      ] as Item[],
      fetch_vehicle_type_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_firmware_vehicle_type_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  computed: {
    currentTab(): string {
      return this.$route.params.tab || 'overview'
    },
  },
  mounted() {
    this.fetch_vehicle_type_task.setAction(fetchVehicleType)
    this.fetch_firmware_vehicle_type_task.setAction(fetchFirmwareVehicleType)
  },
})
</script>
