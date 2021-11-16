<template>
  <Iframe
    :source="service_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import Iframe from '@/components/utils/iframe.vue'

export default Vue.extend({
  name: 'VersionChooser',
  components: {
    Iframe,
  },
  data() {
    return {
      service_path: '/version-chooser',
    }
  },
})
</script>
