<template>
  <div>
    <v-row class="mt-5">
      <v-col
        cols="12"
        sm="7"
      >
        <v-card class="pa-5 ma-2">
          <vehicle-viewer
            noannotations
            :autorotate="true"
          />
        </v-card>
      </v-col>
      <v-col
        cols="12"
        sm="5"
      >
        <vehicle-info :autorotate="true" />
        <param-sets />
      </v-col>
    </v-row>
    <v-sheet class="d-flex">
      <lights-info />
      <gripper-info />
      <leak-info />
      <power-info />
    </v-sheet>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import VehicleInfo from '@/components/vehiclesetup/overview/VehicleInfo.vue'
import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'

import GripperInfo from './overview/gripper.vue'
import LeakInfo from './overview/LeakInfo.vue'
import LightsInfo from './overview/LightsInfo.vue'
import ParamSets from './overview/ParamSets.vue'
import PowerInfo from './overview/PowerInfo.vue'

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
  },
})
</script>
