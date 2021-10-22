<template>
  <span />
</template>

<script lang="ts">
import axios, { AxiosResponse } from 'axios'
import Vue from 'vue'

import notifications from '@/store/notifications'
import video from '@/store/video'
import { video_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'VideoUpdater',
  async mounted() {
    await callPeriodically(this.fetchDevices, 5000)
    await callPeriodically(this.fetchStreams, 5000)
  },
  methods: {
    async fetchDevices(): Promise<void> {
      await axios({
        method: 'get',
        url: `${video.API_URL}/v4l`,
        timeout: 10000,
      })
        .then((response: AxiosResponse) => {
          video.setAvailableDevices(response.data)
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            video_manager_service,
            'VIDEO_DEVICES_FETCH_FAIL',
            `Could not fetch video devices: ${error.message}`,
          ))
        })
    },
    async fetchStreams(): Promise<void> {
      await axios({
        method: 'get',
        url: `${video.API_URL}/streams`,
        timeout: 10000,
      })
        .then((response: AxiosResponse) => {
          video.setAvailableStreams(response.data)
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            video_manager_service,
            'VIDEO_STREAMS_FETCH_FAIL',
            `Could not fetch video streams: ${error.message}`,
          ))
        })
    },
  },
})
</script>
