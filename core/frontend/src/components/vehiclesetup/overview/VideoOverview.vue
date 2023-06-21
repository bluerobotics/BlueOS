<template>
  <v-card class="ma-2 pa-2">
    <v-card-title class="align-center">
      Video
    </v-card-title>

    <v-card-text
      v-for="device in devices"
      :key="device.source"
      class="ma-2 pa-2"
    >
      <span class="d-block">
        <v-tooltip bottom>
          <template #activator="{ on, attrs }">
            <v-icon
              class="mr-2"
              v-bind="attrs"
              v-on="on"
            >
              mdi-video-box
            </v-icon>
          </template>
          <video-thumbnail
            height="auto"
            width="auto"
            :source="device.source"
            register
          />
        </v-tooltip>
        <b>{{ device.name }}</b></span>
      <span
        v-for="endpoint in streams_for_device[device.name]?.endpoints ?? ['No streams configured'] "
        :key="endpoint"
        class="d-block ml-3"
      >
        {{ endpoint }}
      </span>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">

import Vue from 'vue'

import VideoThumbnail from '@/components/video-manager/VideoThumbnail.vue'
import video from '@/store/video'
import { Dictionary } from '@/types/common'
import {
  Device, Format, StreamInformation, VideoEncodeType,
} from '@/types/video'
import { callPeriodically, stopCallingPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'VideoOverview',
  components: {
    VideoThumbnail,
  },
  computed: {
    streams() {
      return video.available_streams
    },

    devices() {
      function has_supported_encode(device: Device): boolean {
        return device.formats.some((format: Format) => format.encode === VideoEncodeType.H264)
      }
      const devices = video.available_devices
      const valid_devices = devices.filter(
        (device) => device.name !== 'Fake source'
          && !device.name.startsWith('bcm')
          && !device.name.startsWith('Redirect ')
          && has_supported_encode(device),
      )
      return valid_devices
    },
    streams_for_device(): Dictionary<StreamInformation> {
      const streams_for_device: Dictionary<StreamInformation> = {}
      for (const device of this.devices) {
        for (const stream of this.streams) {
          let source = null
          if ('Gst' in stream.video_and_stream.video_source) {
            continue
          }
          if ('Local' in stream.video_and_stream.video_source) {
            source = stream.video_and_stream.video_source.Local.device_path
          }
          if (source === device.source) {
            streams_for_device[`${device.name}`] = stream.video_and_stream.stream_information
          }
        }
      }
      return streams_for_device
    },

  },
  mounted() {
    callPeriodically(video.fetchDevices, 20000)
    callPeriodically(video.fetchStreams, 20000)
  },
  beforeDestroy() {
    stopCallingPeriodically(video.fetchDevices)
    stopCallingPeriodically(video.fetchStreams)
  },
})
</script>

<style scoped>
.canera-icon {
  display: block;
  margin: auto;
}
</style>
