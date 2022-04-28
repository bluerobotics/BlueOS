<template>
  <v-card
    elevation="0"
    class="video-manager"
  >
    <div
      v-if="are_video_devices_available && !updating_devices"
      class="videos-list"
    >
      <template
        v-for="(device, index) in video_devices"
      >
        <v-divider
          v-if="index!==0"
          :key="index"
        />
        <video-device
          :key="device.source"
          :device="device"
        />
      </template>
    </div>
    <spinning-logo
      v-else-if="updating_devices"
      size="30%"
      subtitle="Fetching available video devices..."
    />
    <v-card
      v-else
      class="mx-auto my-12 pa-8 text-h6 text-center"
      width="300"
    >
      No video-devices available.
    </v-card>
    <video-updater />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import settings from '@/libs/settings'
import video from '@/store/video'
import { Device, Format, VideoEncodeType } from '@/types/video'

import VideoDevice from './VideoDevice.vue'
import VideoUpdater from './VideoUpdater.vue'

export default Vue.extend({
  name: 'VideoManager',
  components: {
    VideoDevice,
    VideoUpdater,
    SpinningLogo,
  },
  computed: {
    are_video_devices_available(): boolean {
      return this.video_devices.length !== 0
    },
    video_devices(): Device[] {
      // Check if a device provides H264
      function has_h264(device: Device): boolean {
        return device.formats.filter((format: Format) => format.encode === VideoEncodeType.H264).length !== 0
      }

      function should_show(device: Device): boolean {
        return device.name !== 'Fake source' || settings.is_pirate_mode
      }

      return video.available_devices
        .filter(has_h264)
        .filter(should_show)
        .sort((a: Device, b: Device) => a.name.localeCompare(b.name))
    },
    updating_devices(): boolean {
      return video.updating_devices
    },
  },
})
</script>

<style scoped>
.video-manager {
  max-width: 700px;
  margin: auto;
  background-color: transparent;
}
.videos-list {
  margin: 30px 15px;
  background-color: transparent;
}
</style>
