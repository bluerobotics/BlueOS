<template>
  <iframe
    loading="lazy"
    :src="service_path"
    height="100%"
    width="100%"
  />
</template>

<script lang="ts">
import Vue from 'vue'

export default Vue.extend({
  name: 'FileBrowserView',
  data() {
    return {
      service_path: '/file-browser',
    }
  },
})
</script>
