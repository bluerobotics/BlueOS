<template>
  <generic-viewer
    :highlight="highlight"
    :noannotations="noannotations"
    :autorotate="autorotate"
    :transparent="transparent"
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
    transparent: {
      type: Boolean,
      required: false,
      default: false,
    },
    highlight: {
      type: Array<string>,
      required: false,
      default: () => [],
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
