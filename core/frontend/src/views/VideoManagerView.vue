<template>
  <video-manager />
</template>

<script lang="ts">
import Vue from 'vue'

import VideoManager from '@/components/video-manager/VideoManager.vue'

export default Vue.extend({
  name: 'VideoManagerView',
  components: {
    VideoManager,
  },
})
</script>
