<template>
  <v-card
    width="100%"
    class="pa-0 my-4"
  >
    <div class="d-flex flex-no-wrap align-center justify-space-between">
      <div>
        <v-card-title>{{ stream.video_and_stream.name }}</v-card-title>
        <v-card-subtitle>{{ settings_summary }}</v-card-subtitle>
        <p class="pl-4">
          Status: {{ stream.running ? 'running' : 'Not running' }}
        </p>
      </div>
      <div>
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
      </div>
      <div class="mr-4">
        <v-btn
          class="ma-2 red lighten-4"
          elevation="2"
          icon
          @click="deleteStream"
        >
          <v-icon>mdi-delete</v-icon>
        </v-btn>
      </div>
    </div>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'

import VideoStore from '@/store/video'
import { StreamStatus } from '@/types/video'
import { video_dimension_framerate_text } from '@/utils/video'

const video_store: VideoStore = getModule(VideoStore)

export default Vue.extend({
  name: 'VideoStream',
  components: {
  },
  props: {
    stream: {
      type: Object as PropType<StreamStatus>,
      required: true,
    },
  },
  computed: {
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
    async deleteStream(): Promise<void> {
      video_store.deleteStream(this.stream)
    },
  },
})
</script>
