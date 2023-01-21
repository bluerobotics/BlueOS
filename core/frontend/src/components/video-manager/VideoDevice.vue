<template>
  <v-card
    width="100%"
    class="pa-2 my-4"
  >
    <div class="d-flex flex-column flex-sm-row align-center justify-space-between ma-4">
      <div class="d-flex flex-column align-center align-sm-start">
        <p class="font-weigth-medium text-sm-h6 ma-0">
          {{ device.name }}
        </p>
        <p class="text-subtitle-2 font text--secondary ma-0">
          {{ device.source }}
        </p>
        <v-btn
          class="my-2"
          @click="openControlsDialog"
        >
          <v-icon>mdi-cog</v-icon>
          Configure
        </v-btn>
        <v-btn
          class="my-2"
          :disabled="are_video_streams_available || updating_streams"
          @click="openStreamCreationDialog"
        >
          <v-icon>mdi-plus</v-icon>
          Add stream
        </v-btn>
      </div>
      <div>
        <video-thumbnail
          v-if="$vuetify.breakpoint.smAndUp"
          height="auto"
          width="280"
          :source="device.source"
          :register="are_video_streams_available"
        />
      </div>
    </div>
    <v-card flat>
      <v-container v-if="are_video_streams_available && !updating_streams">
        <v-row>
          <v-col
            v-for="(stream, i) in device_streams"
            :key="i"
          >
            <video-stream
              :stream="stream"
              :device="device"
            />
          </v-col>
        </v-row>
      </v-container>
      <v-container v-else-if="updating_streams">
        <spinning-logo
          size="10%"
          subtitle="Fetching available streams..."
        />
      </v-container>
    </v-card>
    <video-controls-dialog
      v-model="show_controls_dialog"
      :device="device"
    />
    <video-stream-creation-dialog
      v-model="show_stream_creation_dialog"
      :device="device"
      @streamChange="createNewStream"
    />
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import video from '@/store/video'
import { CreatedStream, Device, StreamStatus } from '@/types/video'

import VideoControlsDialog from './VideoControlsDialog.vue'
import VideoStream from './VideoStream.vue'
import VideoStreamCreationDialog from './VideoStreamCreationDialog.vue'
import VideoThumbnail from './VideoThumbnail.vue'

export default Vue.extend({
  name: 'VideoDevice',
  components: {
    VideoControlsDialog,
    VideoStreamCreationDialog,
    VideoStream,
    VideoThumbnail,
    SpinningLogo,
  },
  props: {
    device: {
      type: Object as PropType<Device>,
      required: true,
    },
  },
  data() {
    return {
      show_controls_dialog: false,
      show_stream_creation_dialog: false,
    }
  },
  computed: {
    are_video_streams_available(): boolean {
      return !this.device_streams.isEmpty()
    },
    device_streams(): StreamStatus[] {
      return this.video_streams.filter((stream) => {
        if ('Gst' in stream.video_and_stream.video_source) {
          return stream.video_and_stream.video_source.Gst.source.Fake === this.device.source
        }
        if ('Local' in stream.video_and_stream.video_source) {
          return stream.video_and_stream.video_source.Local.device_path === this.device.source
        }
        return false
      })
    },
    video_streams(): StreamStatus[] {
      return video.available_streams
    },
    updating_streams(): boolean {
      return video.updating_streams
    },
  },
  methods: {
    openControlsDialog(): void {
      this.show_controls_dialog = true
    },
    openStreamCreationDialog(): void {
      this.show_stream_creation_dialog = true
    },

    async createNewStream(stream: CreatedStream): Promise<void> {
      await video.createStream(stream)
    },
  },
})
</script>
