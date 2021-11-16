<template>
  <Iframe
    :source="service_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import Iframe from '@/components/utils/iframe.vue'

export default Vue.extend({
  name: 'FileBrowserView',
  components: {
    Iframe,
  },
  data() {
    return {
      service_path: '/file-browser',
    }
  },
})
</script>
