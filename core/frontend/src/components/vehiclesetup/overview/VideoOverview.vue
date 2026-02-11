<template>
  <v-card class="pa-2">
    <v-card-title class="align-center">
      Video
    </v-card-title>

    <v-card-text
      v-for="device in devices"
      :key="device.source"
      class="ma-2 pa-2"
    >
      <span class="d-block">
        <v-tooltip bottom :disabled="streams_for_device[device.name] === undefined">
          <template #activator="{ on, attrs }">
            <v-icon
              class="mr-2"
              v-bind="attrs"
              v-on="on"
            >
              mdi-video-box
            </v-icon>
          </template>
          <template #default="{ value }">
            <video-thumbnail
              v-if="value"
              width="280px"
              :source="device.source"
              register
            />
          </template>
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
import { OneMoreTime } from '@/one-more-time'
import video from '@/store/video'
import { Dictionary } from '@/types/common'
import {
  Device, Format, StreamInformation,
  VideoEncodeTypeEnum,
} from '@/types/video'
import { available_streams_from_device } from '@/utils/video'

export default Vue.extend({
  name: 'VideoOverview',
  components: {
    VideoThumbnail,
  },
  data() {
    return {
      fetch_devices_task: new OneMoreTime({ delay: 1000, disposeWith: this }),
      fetch_streams_task: new OneMoreTime({ delay: 1000, disposeWith: this }),
    }
  },
  computed: {
    devices() {
      function has_supported_encode(device: Device): boolean {
        return device.formats.some((format: Format) => format.encode === VideoEncodeTypeEnum.H264)
      }
      const devices = video.available_devices
      const valid_devices = devices.filter(
        (device) => !device.name.toLocaleLowerCase().startsWith('fake')
          && !device.name.toLocaleLowerCase().startsWith('bcm')
          && has_supported_encode(device),
      )
      return valid_devices
    },
    streams_for_device(): Dictionary<StreamInformation> {
      return Object.fromEntries(
        this.devices.flatMap((device) => available_streams_from_device(video.available_streams, device)
          .map((stream) => [
            `${device.name}`,
            stream.video_and_stream.stream_information,
          ])),
      )
    },

  },
  mounted() {
    this.fetch_devices_task.setAction(video.fetchDevices)
    this.fetch_streams_task.setAction(video.fetchStreams)
  },
})
</script>

<style scoped>
.canera-icon {
  display: block;
  margin: auto;
}
</style>
