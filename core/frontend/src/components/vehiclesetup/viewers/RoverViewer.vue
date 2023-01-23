<template>
  <Blueboat-viewer
    v-if="has_3d_model"
    :highlight="highlight"
    :noannotations="noannotations"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'

import BlueboatViewer from './BlueboatViewer.vue'

export default Vue.extend({
  name: 'SubViewer',
  components: {
    BlueboatViewer,
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
    frame_class(): number | undefined {
      return autopilot_data.parameter('FRAME_CLASS')?.value
    },
    has_3d_model(): boolean {
      // TODO: enum this
      return this.frame_class === 2
    },
  },
})
</script>
