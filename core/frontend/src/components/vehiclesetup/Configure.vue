<template>
  <div>
    <v-container fluid>
      <v-tabs
        :value="currentSubtab"
        centered
        show-arrows
      >
        <v-tabs-slider />
        <v-tab
          v-for="page in filtered_pages"
          :key="`title-${page.title}`"
          :to="{ name: 'Vehicle Setup', params: { tab: 'configure', subtab: page.value } }"
        >
          {{ page.title }}
        </v-tab>
      </v-tabs>
      <not-safe-overlay />
      <v-tabs-items :value="currentSubtab">
        <v-tab-item
          v-for="page in filtered_pages"
          :key="`item-${page.title}`"
          :value="page.value"
        >
          <div class="main-container">
            <component :is="page.component" />
          </div>
        </v-tab-item>
      </v-tabs-items>
    </v-container>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import VehicleInfo from '@/components/vehiclesetup/overview/VehicleInfo.vue'
import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'
import autopilot from '@/store/autopilot_manager'

import SpinningLogo from '../common/SpinningLogo.vue'
import ArdupilotAccelerometerSetup from './configuration/accelerometer/ArdupilotAccelerometerSetup.vue'
import ArdupilotVehicleBodySetup from './configuration/ArdupilotVehicleBodySetup.vue'
import Camera from './configuration/camera.vue'
import ArdupilotMavlinkCompassSetup from './configuration/compass/ArdupilotMavlinkCompassSetup.vue'
import FailsafesConfigration from './configuration/failsafes/Failsafes.vue'
import LightsConfigration from './configuration/lights.vue'
import BaroCalib from './overview/BaroCalib.vue'
import GripperInfo from './overview/gripper.vue'
import GyroCalib from './overview/GyroCalib.vue'
import LeakInfo from './overview/LeakInfo.vue'
import LightsInfo from './overview/LightsInfo.vue'
import ParamSets from './overview/ParamSets.vue'
import PowerInfo from './overview/PowerInfo.vue'

export interface Item {
  title: string,
  value: string,
  component: unknown,
  filter?: () => boolean,
}

export default Vue.extend({
  name: 'Configure',
  components: {
    VehicleViewer,
    VehicleInfo,
    GripperInfo,
    PowerInfo,
    LightsInfo,
    LeakInfo,
    ParamSets,
    LightsConfigration,
    ArdupilotMavlinkCompassSetup,
    ArdupilotAccelerometerSetup,
    SpinningLogo,
    GyroCalib,
    BaroCalib,
    FailsafesConfigration,
    Camera,
    NotSafeOverlay,
  },
  data() {
    return {
      pages: [
        { title: 'Parameters', value: 'parameters', component: ParamSets },
        { title: 'Vehicle Body', value: 'vehiclebody', component: ArdupilotVehicleBodySetup },
        { title: 'Gyroscope', value: 'gyroscope', component: GyroCalib },
        { title: 'Accelerometer', value: 'accelerometer', component: ArdupilotAccelerometerSetup },
        { title: 'Compass', value: 'compass', component: ArdupilotMavlinkCompassSetup },
        { title: 'Baro', value: 'baro', component: BaroCalib },
        {
          title: 'Lights',
          value: 'lights',
          component: LightsConfigration,
          filter: () => autopilot.vehicle_type === 'Submarine',
        },
        { title: 'Failsafes', value: 'failsafes', component: FailsafesConfigration },
        { title: 'Camera Gimbal', value: 'camera', component: Camera },
      ] as Item[],
    }
  },
  computed: {
    filtered_pages() {
      return this.pages.filter((page) => page.filter ?? true)
    },
    currentSubtab(): string {
      return this.$route.params.subtab || 'parameters'
    },
  },
})
</script>

<style scoped>
.main-container {
  background-color: var(--v-mariner_blue-base) !important;
}
</style>
