<template>
  <v-card style="max-width: 93%; margin: auto">
    <v-container class="d-flex align-center elevation-0 py-6 px-4" :class="{ 'flex-column': $vuetify.breakpoint.xs }">
      <div class="d-flex flex-column justify-space-between" :class="{ 'align-center': $vuetify.breakpoint.xs }">
        <p class="text-h6 text-no-wrap ma-0">
          {{ stream.video_and_stream.name }}
        </p>
        <p class="text-subtitle-2 text-no-wrap text--secondary ma-0">
          {{ settings_summary }}
        </p>
        <p class="mb-2 mt-6">
          Status: {{ stream.running ? 'running' : 'Not running' }}
        </p>
      </div>
      <v-simple-table dense class="text-center" style="margin: auto">
        <template #default>
          <tbody>
            <tr>
              <td>{{ stream.video_and_stream.stream_information.configuration.encode }}</td>
            </tr>
            <tr v-for="(endpoint, index) in stream.video_and_stream.stream_information.endpoints" :key="index">
              <td>
                {{ endpoint }}
              </td>
            </tr>
            <tr>
              <td>{{ source_path }}</td>
            </tr>
          </tbody>
          <v-btn v-if="isSDPFileAvailable" class="ma-6 elevation-1" small @click="downloadSDPFile">
            <v-icon>mdi-download</v-icon>
            SDP
          </v-btn>
        </template>
      </v-simple-table>
    </v-container>
    <v-btn class="stream-edit-btn elevation-1" color="primary" dark fab small @click="openStreamEditDialog">
      <v-icon>mdi-pencil</v-icon>
    </v-btn>
    <v-btn class="stream-remove-btn elevation-1" color="error" dark fab small @click="deleteStream">
      <v-icon>mdi-delete</v-icon>
    </v-btn>
    <video-stream-creation-dialog
      v-model="show_stream_edit_dialog"
      :device="device"
      finish-button-text="Apply"
      :stream="stream_prototype"
      @streamChange="editStream"
    />
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import video from '@/store/video'
import {
  CreatedStream, Device, StreamPrototype, StreamStatus,
} from '@/types/video'
import { video_dimension_framerate_text } from '@/utils/video'

import VideoStreamCreationDialog from './VideoStreamCreationDialog.vue'

export default Vue.extend({
  name: 'VideoStream',
  components: {
    VideoStreamCreationDialog,
  },
  props: {
    stream: {
      type: Object as PropType<StreamStatus>,
      required: true,
    },
    device: {
      type: Object as PropType<Device>,
      required: true,
    },
  },
  data() {
    return {
      show_stream_edit_dialog: false,
    }
  },
  computed: {
    stream_prototype(): StreamPrototype {
      return {
        name: this.stream.video_and_stream.name,
        encode: this.stream.video_and_stream.stream_information.configuration.encode,
        dimensions: {
          width: this.stream.video_and_stream.stream_information.configuration.width,
          height: this.stream.video_and_stream.stream_information.configuration.height,
        },
        interval: this.stream.video_and_stream.stream_information.configuration.frame_interval,
        endpoints: this.stream.video_and_stream.stream_information.endpoints,
        thermal: this.stream.video_and_stream.stream_information?.extended_configuration?.thermal ?? false,
      }
    },
    settings_summary(): string {
      const { height, width, frame_interval } = this.stream.video_and_stream.stream_information.configuration
      return video_dimension_framerate_text(height, width, frame_interval)
    },
    source_path(): string {
      if ('Gst' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Gst.source.Fake
      }
      if ('Local' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Local.device_path
      }
      return 'Source unavailable'
    },
    isSDPFileAvailable(): boolean {
      return this.stream.video_and_stream.stream_information.endpoints.first()?.startsWith('udp://') ?? false
    },
  },
  methods: {
    openStreamEditDialog(): void {
      this.show_stream_edit_dialog = true
    },
    async editStream(edited_stream: CreatedStream): Promise<void> {
      await video.deleteStream(this.stream)
      await video.createStream(edited_stream)
    },
    async deleteStream(): Promise<void> {
      video.deleteStream(this.stream)
    },
    async downloadSDPFile(): Promise<void> {
      await video.fetchSDP(this.stream)
    },
  },
})
</script>

<style scoped>
.stream-edit-btn {
  position: absolute;
  top: 15%;
  right: -20px;
}
.stream-remove-btn {
  position: absolute;
  bottom: 15%;
  right: -20px;
}
</style>
