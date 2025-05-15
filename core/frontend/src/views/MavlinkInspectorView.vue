<template>
  <BrIframe
    :source="service_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import BrIframe from '@/components/utils/BrIframe.vue'

export default Vue.extend({
  name: 'MavlinkInspectorView',
  components: {
    BrIframe,
  },
  data() {
    return {
      service_path: `${window.location.protocol}//${window.location.hostname}:8080`,
    }
  },
})
</script>
