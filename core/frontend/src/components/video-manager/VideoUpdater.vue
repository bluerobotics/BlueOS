<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import { OneMoreTime } from '@/one-more-time'
import video from '@/store/video'

export default Vue.extend({
  name: 'VideoUpdater',
  data() {
    return {
      fetch_devices_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_streams_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
    }
  },
  mounted() {
    this.fetch_devices_task.setAction(video.fetchDevices)
    this.fetch_streams_task.setAction(video.fetchStreams)
  },
})
</script>
