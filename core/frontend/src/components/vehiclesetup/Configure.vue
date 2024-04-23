<template>
  <div>
    <v-container fluid>
      <v-tabs
        v-model="page_selected"
        centered
        show-arrows
      >
        <v-tabs-slider />
        <v-tab
          v-for="page in filtered_pages"
          :key="`title-${page.title}`"
        >
          {{ page.title }}
        </v-tab>
      </v-tabs>
      <v-tabs-items v-model="page_selected">
        <v-tab-item
          v-for="page in filtered_pages"
          :key="`item-${page.title}`"
        >
          <component :is="page.component" />
        </v-tab-item>
      </v-tabs-items>
    </v-container>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import VehicleInfo from '@/components/vehiclesetup/overview/VehicleInfo.vue'
import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'
import autopilot from '@/store/autopilot_manager'

import SpinningLogo from '../common/SpinningLogo.vue'
import ArdupilotAccelerometerSetup from './configuration/accelerometer/ArdupilotAccelerometerSetup.vue'
import ArdupilotMavlinkCompassSetup from './configuration/compass/ArdupilotMavlinkCompassSetup.vue'
import LightsConfigration from './configuration/lights.vue'
import BaroCalib from './overview/BaroCalib.vue'
import GripperInfo from './overview/gripper.vue'
import LeakInfo from './overview/LeakInfo.vue'
import LightsInfo from './overview/LightsInfo.vue'
import ParamSets from './overview/ParamSets.vue'
import PowerInfo from './overview/PowerInfo.vue'

export interface Item {
  title: string,
  icon: string,
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
  },
  data() {
    return {
      page_selected: null as string | null,
      pages: [
        { title: 'Parameters', component: ParamSets },
        { title: 'Accelerometer', component: ArdupilotAccelerometerSetup },
        { title: 'Compass', component: ArdupilotMavlinkCompassSetup },
        { title: 'Baro', component: BaroCalib },
        { title: 'Gripper', component: undefined },
        { title: 'Lights', component: LightsConfigration, filter: () => autopilot.vehicle_type === 'Submarine' },
        { title: 'Camera Mount', component: undefined },
      ] as Item[],
    }
  },
  computed: {
    filtered_pages() {
      // eslint-disable-next-line no-extra-parens
      return this.pages.filter((page) => (page.filter ? page.filter() : true))
    },
  },
})
</script>
