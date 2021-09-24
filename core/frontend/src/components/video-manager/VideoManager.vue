<template>
  <v-card
    class="mx-auto my-6"
    max-width="1000"
  >
    <v-card-title>Video Manager</v-card-title>
    <v-container>
      <v-row dense>
        <v-col
          class="mr-2"
        >
          <v-card flat>
            <v-container
              v-if="are_video_devices_available && !updating_devices"
            >
              <video-device
                v-for="device in video_devices"
                :key="device.source"
                :device="device"
              />
            </v-container>
            <v-container v-else-if="updating_devices">
              <spinning-logo size="30%" />
            </v-container>
            <v-container
              v-else
              class="text-h6 text-center"
            >
              No video-devices available.
            </v-container>
          </v-card>
        </v-col>
      </v-row>
    </v-container>
    <video-updater />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import VideoStore from '@/store/video'
import { Device } from '@/types/video'

import VideoDevice from './VideoDevice.vue'
import VideoUpdater from './VideoUpdater.vue'

const video_store: VideoStore = getModule(VideoStore)

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
      return video_store.available_devices
    },
    updating_devices(): boolean {
      return video_store.updating_devices
    },
  },
})
</script>
