<template>
  <generic-viewer
    :highlight="highlight"
    :noannotations="noannotations"
    :autorotate="autorotate"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import GenericViewer from './GenericViewer.vue'

export default Vue.extend({
  name: 'VehicleViewer',
  components: {
    GenericViewer,
  },
  props: {
    highlight: {
      type: String,
      required: false,
      default: null,
    },
    autorotate: {
      type: Boolean,
      required: true,
    },
    noannotations: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
})
</script>
