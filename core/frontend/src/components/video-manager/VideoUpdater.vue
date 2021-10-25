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
  async mounted() {
    await callPeriodically(this.fetchDevices, 5000)
    await callPeriodically(this.fetchStreams, 5000)
  },
  methods: {
    async fetchDevices(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${video.API_URL}/v4l`,
        timeout: 10000,
      })
        .then((response) => {
          video.setAvailableDevices(response.data)
        })
        .catch((error) => {
          video.setAvailableDevices([])
          if (error === backend_offline_error) { return }
          const message = `Could not fetch video devices: ${error.message}`
          notifications.pushError({ service: video_manager_service, type: 'VIDEO_DEVICES_FETCH_FAIL', message })
        })
    },
    async fetchStreams(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${video.API_URL}/streams`,
        timeout: 10000,
      })
        .then((response) => {
          video.setAvailableStreams(response.data)
        })
        .catch((error) => {
          video.setAvailableStreams([])
          if (error === backend_offline_error) { return }
          const message = `Could not fetch video streams: ${error.message}`
          notifications.pushError({ service: video_manager_service, type: 'VIDEO_STREAMS_FETCH_FAIL', message })
        })
    },
  },
})
</script>
