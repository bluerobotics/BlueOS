<template>
  <BrIframe
    :source="full_path"
  />
</template>

<script lang="ts">
import Vue from 'vue'

import BrIframe from '@/components/utils/BrIframe.vue'

export default Vue.extend({
  name: 'FileBrowserView',
  components: {
    BrIframe,
  },
  data() {
    return {
      service_path: '/file-browser/',
    }
  },
  computed: {
    full_path() {
      return `${this.service_path}${this.$route.params.path ?? ''}`
    },
  },
})
</script>
