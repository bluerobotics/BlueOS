<!-- eslint-disable vuejs-accessibility/click-events-have-key-events -->
<template>
  <v-card style="min-width: 300px;">
    <v-container>
      <div class="stream-info-grid">
        <div class="info-label">
          Stream Name:
        </div>
        <div class="info-value">
          {{ stream.video_and_stream.name }}
        </div>

        <div class="info-label">
          Format:
        </div>
        <div class="info-value">
          {{ format }}
        </div>

        <div class="info-label">
          Encoding:
        </div>
        <div class="info-value">
          {{ encode }}
        </div>

        <div class="info-label">
          Endpoints:
        </div>
        <div class="info-value wrap-commas">
          <span v-for="(endpoint, idx) in stream.video_and_stream.stream_information.endpoints" :key="endpoint">
            {{ endpoint }}<span v-if="idx !== stream.video_and_stream.stream_information.endpoints.length - 1">, </span>
          </span>
        </div>

        <div class="info-label">
          Source:
        </div>
        <div class="info-value text-truncate">
          {{ source_path }}
        </div>

        <div class="info-label">
          Status:
        </div>
        <div class="info-value">
          {{ stream.running ? 'Running' : 'Not running' }}
        </div>

        <template v-if="(!stream.running) && stream.error">
          <div class="info-label error--text font-weight-bold">
            Errors:
          </div>
          <div class="info-value error-content">
            <v-textarea
              class="text-caption stream-error-textarea"
              :rows="isExpanded ? 12 : 1"
              :auto-grow="!isExpanded"
              readonly
              :value="streamErrorText"
              hide-details
              flat
              dense
            />
            <div class="d-flex justify-end align-center pr-4">
              <v-btn
                small
                text
                class="mr-2"
                @click.stop="copyVideoStreamToClipboard"
              >
                <v-icon small left>
                  mdi-content-copy
                </v-icon>
                Copy
              </v-btn>
              <v-btn
                small
                text
                class="mr-2"
                @click.stop="toggleExpandStreamError"
              >
                <v-icon
                  v-if="isExpanded"
                  small
                  left
                >
                  mdi-chevron-up
                </v-icon>
                <v-icon
                  v-else
                  small
                  left
                >
                  mdi-chevron-down
                </v-icon>
                {{ isExpanded ? "Show less" : "Show more" }}
              </v-btn>
            </div>
          </div>
        </template>
      </div>
    </v-container>

    <v-card-actions class="actions-container">
      <v-btn
        v-if="isEditable"
        v-tooltip="'Edit stream'"
        class="stream-edit-btn elevation-1"
        color="primary"
        dark
        fab
        small
        @click="openStreamEditDialog"
      >
        <v-icon>mdi-pencil</v-icon>
      </v-btn>
      <v-btn
        v-if="isRemovable"
        v-tooltip="'Remove stream'"
        class="stream-remove-btn elevation-1"
        color="error"
        dark
        fab
        small
        @click="deleteStream"
      >
        <v-icon>mdi-delete</v-icon>
      </v-btn>
      <v-btn
        v-if="isSDPFileAvailable"
        v-tooltip="'Download SDP to file'"
        class="stream-edit-btn elevation-1"
        color="grey"
        dark
        fab
        small
        @click="downloadSDPFile"
      >
        <div class="d-flex flex-column align-center">
          <span class="text-caption font-weight-bold pt-2 pb-1">SDP</span>
          <v-icon class="pb-4">
            mdi-file-download
          </v-icon>
        </div>
      </v-btn>
      <v-btn
        v-if="isSDPFileAvailable"
        v-tooltip="'Copy SDP file URL'"
        class="stream-edit-btn elevation-1"
        color="grey"
        dark
        fab
        small
        @click="copySDPFileURL"
      >
        <div class="d-flex flex-column align-center">
          <span class="text-caption font-weight-bold pt-2 pb-1">SDP</span>
          <v-icon class="pb-4">
            mdi-file-link
          </v-icon>
        </div>
      </v-btn>
    </v-card-actions>

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

import { copyToClipboard } from '@/cosmos'
import video from '@/store/video'
import {
  CreatedStream, Device, StreamPrototype, StreamStatus,
} from '@/types/video'
import back_axios from '@/utils/api'
import { video_dimension_framerate_text, video_encode_text } from '@/utils/video'

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
      isExpanded: false,
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
    format(): string {
      const { height, width, frame_interval } = this.stream.video_and_stream.stream_information.configuration
      return video_dimension_framerate_text(height, width, frame_interval)
    },
    encode(): string {
      const { encode } = this.stream.video_and_stream.stream_information.configuration
      return video_encode_text(encode)
    },
    source_path(): string {
      if ('Gst' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Gst.source.Fake
      }
      if ('Local' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Local.device_path
      }
      if ('Onvif' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Onvif.source.Onvif
      }
      if ('Redirect' in this.stream.video_and_stream.video_source) {
        return this.stream.video_and_stream.video_source.Redirect.source.Redirect
      }
      return 'Source unavailable'
    },
    isSDPFileAvailable(): boolean {
      return this.stream.video_and_stream.stream_information.endpoints.first()?.startsWith('udp://') ?? false
    },
    sDPFileURL(): string {
      return `${window.location.origin}${video.API_URL}/sdp?source=${encodeURIComponent(this.source_path)}`
    },
    streamErrorText(): string | null {
      if (this.stream.error === null) {
        return null
      }

      if (this.stream.error === '') {
        return 'Unknown. See Mavlink Camera Manager backend logs for details.'
      }

      const fullText = this.stream.error
        .replaceAll('\\n', '\n').replaceAll(': "', ': \n\n"').replaceAll('". ', '".\n\n')

      if (this.isExpanded) {
        return `${fullText} \n`
      }

      const firstLine = fullText.split('\n')[0]
      return firstLine
    },
    isEditable(): boolean {
      return !('Onvif' in this.stream.video_and_stream.video_source)
    },
    isRemovable(): boolean {
      return !('Onvif' in this.stream.video_and_stream.video_source)
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
      await copyToClipboard(this.sDPFileURL)
    },
    async copyVideoStreamToClipboard(): Promise<void> {
      await copyToClipboard(JSON.stringify(this.$props, null, 2))
    },
    toggleExpandStreamError() {
      this.isExpanded = !this.isExpanded
    },
  },
})
</script>
<style scoped>
.stream-info-grid {
  display: grid;
  grid-template-columns: minmax(100px, max-content) 1fr;
  gap: 0.5rem 1rem;
  padding-top: 10px;
}

.info-label {
  font-weight: 500;
  text-align: right;
  color: var(--v-tuna-base);
}

.info-value {
  overflow-wrap: anywhere;
}

.error-content {
  position: relative;
  padding-bottom: 25px;
}

.actions-container {
    position: absolute;
    top: -28px;
    right: 0;
    display: flex;
    flex-direction: row;
  }

.action-buttons {
  position: relative;
}

@media (max-width: 600px) {
  .stream-info-grid {
    grid-template-columns: 1fr;
  }

  .info-label {
    text-align: left;
    padding-right: 0;
    margin-top: 0.5rem;
  }

  .info-label:first-child {
    margin-top: 0;
  }

  .action-buttons {
    justify-content: center;
    width: 100%;
  }
}
</style>
