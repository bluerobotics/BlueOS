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
import axios from 'axios'
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationStore from '@/store/notifications'
import VideoStore from '@/store/video'
import { video_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { StreamStatus } from '@/types/video'
import { video_dimension_framerate_text } from '@/utils/video'

const video_store: VideoStore = getModule(VideoStore)
const notification_store: NotificationStore = getModule(NotificationStore)

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
      video_store.setUpdatingStreams(true)

      await axios({
        method: 'delete',
        url: `${video_store.API_URL}/delete_stream`,
        timeout: 10000,
        params: { name: this.stream.video_and_stream.name },
      })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            video_manager_service,
            'VIDEO_STREAM_DELETE_FAIL',
            `Could not delete video stream: ${error.message}.`,
          ))
        })
    },
  },
})
</script>
