<template>
  <BluerovViewer
    v-if="has_3d_model"
    :highlight="highlight"
    :noannotations="noannotations"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import { FRAME_CONFIG } from '@/types/autopilot/parameter-sub-enums'

import BluerovViewer from './BluerovViewer.vue'

export default Vue.extend({
  name: 'SubViewer',
  components: {
    BluerovViewer,
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
    frame_type(): number | undefined {
      return autopilot_data.parameter('FRAME_CONFIG')?.value
    },
    has_3d_model(): boolean {
      return this.frame_type !== undefined
        && [FRAME_CONFIG.VECTORED_6DOF, FRAME_CONFIG.VECTORED].includes(this.frame_type)
    },
  },
})
</script>
