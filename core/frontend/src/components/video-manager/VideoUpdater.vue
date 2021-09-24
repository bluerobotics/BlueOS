<template>
  <span />
</template>

<script lang="ts">
import axios, { AxiosResponse } from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationStore from '@/store/notifications'
import VideoStore from '@/store/video'
import { video_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

const video_store: VideoStore = getModule(VideoStore)
const notification_store: NotificationStore = getModule(NotificationStore)

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
        url: `${video_store.API_URL}/v4l`,
        timeout: 10000,
      })
        .then((response: AxiosResponse) => {
          video_store.setAvailableDevices(response.data)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
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
        url: `${video_store.API_URL}/streams`,
        timeout: 10000,
      })
        .then((response: AxiosResponse) => {
          video_store.setAvailableStreams(response.data)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
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
