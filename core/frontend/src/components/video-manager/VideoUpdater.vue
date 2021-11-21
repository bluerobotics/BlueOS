<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import notifications from '@/store/notifications'
import video from '@/store/video'
import { video_manager_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'VideoUpdater',
  mounted() {
    callPeriodically(video.fetchDevices, 5000)
    callPeriodically(video.fetchStreams, 5000)
  },
})
</script>
