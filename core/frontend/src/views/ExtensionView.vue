<template>
  <Iframe
    :source="service_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import Iframe from '@/components/utils/iframe.vue'

export default Vue.extend({
  name: 'ExtensionView',
  components: {
    Iframe,
  },
  computed: {
    service_path() {
      return `${window.location.protocol}//${window.location.hostname}:${this.$route.params.port}`
    },
  },
})
</script>
