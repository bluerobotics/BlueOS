<template>
  <div class="mx-2">
    <v-row class="mt-5">
      <v-col
        cols="12"
        sm="7"
        class="d-flex"
      >
        <v-card class="pa-5 flex-grow-1 d-flex flex-column">
          <vehicle-viewer
            :highlight="highlight"
            noannotations
            :autorotate="true"
            class="flex-grow-1"
            :style="{
              'min-height': '400px',
              width: '100%',
            }"
          />
        </v-card>
      </v-col>
      <v-col
        cols="12"
        sm="5"
      >
        <vehicle-info :autorotate="true" />
        <onboard-sensors />
      </v-col>
    </v-row>
    <v-row class="mt-5 mb-5">
      <v-col
        v-for="component in bottomComponents"
        :key="component"
        cols="12"
        sm="6"
        md="4"
      >
        <component
          :is="component"
          class="fill-height"
        />
      </v-col>
    </v-row>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import OnboardSensors from '@/components/vehiclesetup/overview/OnboardSensors.vue'
import VehicleInfo from '@/components/vehiclesetup/overview/VehicleInfo.vue'
import VehicleViewer from '@/components/vehiclesetup/viewers/VehicleViewer.vue'

import GripperInfo from './overview/gripper.vue'
import LeakInfo from './overview/LeakInfo.vue'
import LightsInfo from './overview/LightsInfo.vue'
import PingInfo from './overview/PingInfo.vue'
import PowerInfo from './overview/PowerInfo.vue'
import VideoOverview from './overview/VideoOverview.vue'

export default Vue.extend({
  name: 'SetupOverview',
  components: {
    VehicleViewer,
    OnboardSensors,
    VehicleInfo,
    GripperInfo,
    PingInfo,
    PowerInfo,
    LightsInfo,
    LeakInfo,
    VideoOverview,
  },
  data() {
    return {
      highlight: null as string | null,
      bottomComponents: [
        'ping-info',
        'video-overview',
        'lights-info',
        'gripper-info',
        'leak-info',
        'power-info',
      ],
    }
  },
})
</script>
