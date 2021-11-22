<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import video from '@/store/video'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'VideoUpdater',
  mounted() {
    callPeriodically(video.fetchDevices, 5000)
    callPeriodically(video.fetchStreams, 5000)
  },
})
</script>
