<template>
  <v-card style="max-width: 93%; margin: auto">
    <v-container
      class="d-flex align-center justify-space-around elevation-0 py-6 px-4"
      :class="{ 'flex-column': $vuetify.breakpoint.xs }"
    >
      <div class="d-flex flex-column justify-space-between" :class="{ 'align-center': $vuetify.breakpoint.xs }">
        <p class="text-h6 ma-0">
          {{ stream.video_and_stream.name }}
        </p>
        <p class="text-subtitle-2 text-no-wrap text--secondary ma-0">
          {{ settings_summary }}
        </p>
        <p class="mb-2 mt-6">
          Status: {{ stream.running ? 'running' : 'Not running' }}
        </p>
      </div>
      <div class="d-flex ma-6 flex-column" :class="{ 'align-right': $vuetify.breakpoint.xs }">
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
          </template>
        </v-simple-table>
        <div v-if="isSDPFileAvailable" style="min-width: 180px;" class="ma-2 justify-space-between">
          SDP file:
          <v-btn v-tooltip="'Download to file'" class="ma-1 elevation-1" small @click="downloadSDPFile">
            <v-icon>mdi-download</v-icon>
          </v-btn>
          <v-btn v-tooltip="'Copy URL to clipboard'" class="ma-1 elevation-1" small @click="copySDPFileURL">
            <v-icon>mdi-file-link</v-icon>
          </v-btn>
        </div>
      </div>
    </v-container>
    <div style="align-content: space-between">
      <v-btn class="stream-edit-btn elevation-1" color="primary" dark fab small @click="openStreamEditDialog">
        <v-icon>mdi-pencil</v-icon>
      </v-btn>
      <v-btn class="stream-remove-btn elevation-1" color="error" dark fab small @click="deleteStream">
        <v-icon>mdi-delete</v-icon>
      </v-btn>
    </div>
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
import { saveAs } from 'file-saver'
import Vue, { PropType } from 'vue'

import video from '@/store/video'
import {
  CreatedStream, Device, StreamPrototype, StreamStatus,
} from '@/types/video'
import back_axios from '@/utils/api'
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
      let dimensions
      if (this.stream.video_and_stream.stream_information.configuration.width
        && this.stream.video_and_stream.stream_information.configuration.height) {
        dimensions = {
          width: this.stream.video_and_stream.stream_information.configuration.width,
          height: this.stream.video_and_stream.stream_information.configuration.height,
        }
      }
      return {
        name: this.stream.video_and_stream.name,
        encode: this.stream.video_and_stream.stream_information.configuration.encode,
        dimensions,
        interval: this.stream.video_and_stream.stream_information.configuration.frame_interval,
        endpoints: this.stream.video_and_stream.stream_information.endpoints,
        thermal: this.stream.video_and_stream.stream_information?.extended_configuration?.thermal ?? false,
        disable_mavlink:
          this.stream.video_and_stream.stream_information?.extended_configuration?.disable_mavlink ?? false,
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
    sDPFileURL(): string {
      return `${window.location.origin}${video.API_URL}/sdp?source=${encodeURIComponent(this.source_path)}`
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
      const url = this.sDPFileURL
      back_axios({
        method: 'get',
        url,
        timeout: 10000,
        responseType: 'text',
      })
        .then((response) => {
          if (response.status === 200) {
            saveAs(new Blob([response.data], { type: 'application/sdp' }), `${this.device.name}.sdp`)
          }
        })
        .catch((error) => {
          console.error(`Failed downloading SDP file for url ${URL}. Reason: ${error}`)
        })
    },
    async copySDPFileURL(): Promise<void> {
      const try_fallback_clipboard_copy_method = (): void => {
        // If we don't have the permission, fallback to the old hacky way of creating an input,
        // copying the text from it, and destroy it even before it renders.
        const temporaryInputElement = document.createElement('input')
        temporaryInputElement.value = this.sDPFileURL
        document.body.appendChild(temporaryInputElement)

        try {
          temporaryInputElement.select()
          document.execCommand('copy')
        } catch (error) {
          console.error(`Failed to copy URL to clipboard. Reason: ${error}`)
        } finally {
          document.body.removeChild(temporaryInputElement)
        }
      }

      const clipboard_copy_api = (): void => {
        navigator.clipboard.writeText(this.sDPFileURL).catch((error) => {
          console.error(`Failed to copy URL to clipboard using Clipboard API. Reason: ${error}`)
          try_fallback_clipboard_copy_method()
        })
      }

      navigator.permissions
        .query({ name: 'clipboard-write' as PermissionName })
        .then((permissionStatus) => {
          if (permissionStatus.state === 'granted') {
            clipboard_copy_api()
          } else if (permissionStatus.state === 'prompt') {
            // The user will be prompted to grant the permission.
            permissionStatus.onchange = () => {
              if (permissionStatus.state === 'granted') {
                clipboard_copy_api()
              } else {
                try_fallback_clipboard_copy_method()
              }
            }
          } else {
            try_fallback_clipboard_copy_method()
          }
        })
        .catch((error) => {
          console.error('Error while requesting clipboard-write permission:', error)
          try_fallback_clipboard_copy_method()
        })
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
