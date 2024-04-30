<template>
  <div class="main-container">
    <v-card v-if="params_finished_loaded" outline class="pa-5 mt-4 mr-2 mb-2">
      <v-card v-if="params_finished_loaded" outline class="pa-5 mt-4 mr-2 mb-2">
        <v-card-title>
          Frame <parameter-label :param="frame_parameter" label="" />
        </v-card-title>
        <InlineParameterEditor
          v-if="frame_parameter"
          :param="frame_parameter"
          :label="'Frame Configuration'"
          :auto-set="true"
        />
        <InlineParameterEditor
          v-if="frame_type_parameter"
          :param="frame_type_parameter"
          :label="'Frame Subtype'"
          :auto-set="true"
        />
      </v-card>
      <OrientationPicker
        v-if="params_finished_loaded"
        :component-model="current_board"
        :parameter="orientation_parameter"
      />
    </v-card>
  </div>
</template>
<script lang="ts">
import Vue from 'vue'

import {
  fetchCurrentBoard,
} from '@/components/autopilot/AutopilotManagerUpdater'
import OrientationPicker from '@/components/vehiclesetup/OrientationPicker.vue'
import { OneMoreTime } from '@/one-more-time'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'ArdupilotVehicleBodySetup',
  components: {
    OrientationPicker,
  },
  data() {
    return {
      fetch_board_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  computed: {
    current_board(): string | undefined {
      return autopilot.current_board?.name
    },
    orientation_parameter(): Parameter | undefined {
      return autopilot_data.parameter('AHRS_ORIENTATION')
    },
    params_finished_loaded(): boolean {
      return autopilot_data.finished_loading
    },
    frame_parameter(): Parameter | undefined {
      return autopilot_data.parameter('FRAME_CONFIG') || autopilot_data.parameter('FRAME_CLASS')
    },
    frame_type_parameter(): Parameter | undefined {
      switch (autopilot_data.vehicle_type) {
        case 'Submarine':
        case 'Surface Boat':
          return autopilot_data.parameter('FRAME_TYPE')
        case 'Ground Rover':
          return autopilot_data.parameter('FRAME_CLASS')
        default:
          return undefined
      }
    },
  },
  mounted() {
    this.fetch_board_task.setAction(() => fetchCurrentBoard())
    this.fetch_board_task.start()
  },
})
</script>
<style scoped="true">
.main-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
}

td {
  padding-left: 5px !important;
  padding-right: 5px !important;
}

</style>
