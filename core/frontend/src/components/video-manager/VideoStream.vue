<template>
  <v-card
    width="100%"
    class="pa-0 my-4"
  >
    <v-container>
      <v-row align="center">
        <v-col cols="5">
          <v-card-title>{{ stream.video_and_stream.name }}</v-card-title>
          <v-card-subtitle>{{ settings_summary }}</v-card-subtitle>
          <p class="pl-4">
            Status: {{ stream.running ? 'running' : 'Not running' }}
          </p>
        </v-col>
        <v-col cols="5">
          <v-simple-table
            dense
            class="text-center"
          >
            <template #default>
              <tbody>
                <tr>
                  <td>{{ stream.video_and_stream.stream_information.configuration.encode }}</td>
                </tr>
                <tr>
                  <td>{{ stream.video_and_stream.stream_information.endpoints[0] }}</td>
                </tr>
                <tr>
                  <td>{{ source_path }}</td>
                </tr>
              </tbody>
            </template>
          </v-simple-table>
        </v-col>
        <v-col cols="2">
          <v-btn
            class="ma-2 blue lighten-4"
            elevation="2"
            icon
            @click="openStreamEditDialog"
          >
            <v-icon>mdi-pencil</v-icon>
          </v-btn>
          <v-btn
            class="ma-2 red lighten-4"
            elevation="2"
            icon
            @click="deleteStream"
          >
            <v-icon>mdi-delete</v-icon>
          </v-btn>
        </v-col>
      </v-row>
    </v-container>
    <video-stream-creation-dialog
      v-model="show_stream_edit_dialog"
      :device="device"
      finish-button-text="Edit"
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
        endpoint: this.stream.video_and_stream.stream_information.endpoints[0],
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
      } if ('Local' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Local.device_path
      }
      return 'Source unavailable'
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
  },
})
</script>
