<template>
  <v-card class="pa-2 my-4">
    <div class="d-flex flex-column flex-sm-row justify-space-between ma-7">
      <div class="d-flex flex-column align-start align-sm-start">
        <div class="d-flex align-center align-sm-start">
          <v-tooltip top>
            <template #activator="{ on, attrs }">
              <v-icon
                small
                class="mr-2 mt-sm-2"
                :color="status_color"
                v-bind="attrs"
                v-on="on"
              >
                mdi-circle
              </v-icon>
            </template>
            <span v-if="device.blocked">
              Video source is blocked
            </span>
            <span v-else-if="!are_video_streams_available">
              No streams added to this video source
            </span>
            <span v-else-if="has_healthy_streams">
              Streams active
            </span>
            <span v-else>
              Streams stopped, see the errors for more information
            </span>
          </v-tooltip>
          <p class="font-weigth-medium text-sm-h6 ma-0">
            {{ device.name }}
          </p>
        </div>
        <p class="text-subtitle-2 font text--secondary ma-0">
          {{ device.source }}
        </p>
        <div class="d-flex flex-column my-2 justify-space-around">
          <v-btn
            class="my-1"
            :disabled="!has_configs"
            @click="openControlsDialog"
          >
            <v-icon>mdi-tune-variant</v-icon>
            Device Controls
          </v-btn>
          <v-btn
            class="my-1"
            :disabled="device.blocked || (!is_redirect_source && (are_video_streams_available || updating_streams))"
            @click="openStreamCreationDialog"
          >
            <v-icon>mdi-plus</v-icon>
            Add stream
          </v-btn>
          <v-switch
            v-if="is_pirate_mode"
            :input-value="device.blocked"
            dense
            hide-details
            class="mt-2"
            label="Block source"
            @change="toggleBlocked"
          />
        </div>
      </div>
      <div>
        <video-thumbnail
          width="280"
          :source="device.source"
          :register="are_video_streams_available && has_healthy_streams && !thumbnails_disabled"
          :disabled="thumbnails_disabled"
        />
      </div>
    </div>
    <v-container>
      <p v-if="is_redirect_source">
        Redirect sources can be used to redirect the video stream from another device. This is useful to publish
        external streams, such as RTSP from IP cameras, via MAVLink so GCSs can easily find them.
      </p>
    </v-container>
    <v-card flat>
      <v-container v-if="are_video_streams_available && !updating_streams">
        <div
          v-for="(stream, i) in device_streams"
          :key="i"
        >
          <div v-if="i > 0" class="mt-10" />
          <video-stream
            :stream="stream"
            :device="device"
          />
        </div>
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
      :thumbnail-register="are_video_streams_available && has_healthy_streams && !thumbnails_disabled"
      :thumbnail-disabled="thumbnails_disabled"
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
import settings from '@/libs/settings'
import video from '@/store/video'
import {
  CreatedStream, Device, StreamStatus,
} from '@/types/video'
import { available_streams_from_device } from '@/utils/video'

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
    updating_streams(): boolean {
      return video.updating_streams
    },
    device_streams(): StreamStatus[] {
      return available_streams_from_device(video.available_streams, this.device)
    },
    is_redirect_source(): boolean {
      return this.device.source === 'Redirect'
    },
    has_configs(): boolean {
      return !this.device.controls.isEmpty()
    },
    has_healthy_streams(): boolean {
      return this.device_streams.some((stream) => stream.state !== 'stopped')
    },
    thumbnails_disabled(): boolean {
      return this.device_streams.some(
        (stream) => stream.video_and_stream.stream_information?.extended_configuration?.disable_thumbnails === true,
      )
    },
    is_pirate_mode(): boolean {
      return settings.is_pirate_mode
    },
    status_color(): string {
      if (this.device.blocked) {
        return 'warning'
      }
      if (!this.are_video_streams_available) {
        return 'grey'
      }
      if (this.has_healthy_streams) {
        return 'success'
      }
      return 'error'
    },
  },
  methods: {
    openControlsDialog(): void {
      this.show_controls_dialog = true
    },
    openStreamCreationDialog(): void {
      this.show_stream_creation_dialog = true
    },

    async toggleBlocked(): Promise<void> {
      if (this.device.blocked) {
        await video.unblockSource(this.device.source)
      } else {
        await video.blockSource(this.device.source)
      }
    },

    async createNewStream(stream: CreatedStream): Promise<void> {
      await video.createStream(stream)
    },
  },
})
</script>
