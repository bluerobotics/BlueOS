<template>
  <component
    :is="current_viewer"
    :highlight="highlight"
    :noannotations="noannotations"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'

export default Vue.extend({
  name: 'VehicleViewer',
  components: {
    Submarine: () => import('./SubViewer.vue'),
    Rover: () => import('./RoverViewer.vue'),
    None: () => import('./NoneViewer.vue'),
    // TODO: implement a generic viewer for other vehicles
  },
  props: {
    highlight: {
      type: String,
      required: false,
      default: null,
    },
    noannotations: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  computed: {
    vehicle_type() {
      return autopilot.vehicle_type
    },
    current_viewer(): string {
      switch (this.vehicle_type) {
        case 'Submarine':
          return 'Submarine'
        case 'Surface Boat':
          return 'Rover'
        default:
          return 'None'
      }
    },
  },
  methods: {

  },
})
</script>
