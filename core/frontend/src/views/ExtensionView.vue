<template>
  <BrIframe
    :source="service_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import BrIframe from '@/components/utils/BrIframe.vue'

export default Vue.extend({
  name: 'ExtensionView',
  components: {
    BrIframe,
  },
  computed: {
    service_path() {
      return `${window.location.protocol}//${window.location.hostname}:${this.$route.params.port}`
    },
  },
})
</script>
