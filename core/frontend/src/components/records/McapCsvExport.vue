<template>
  <div class="csv-export mt-4 pt-3">
    <div class="d-flex align-center mb-2">
      <span class="subtitle-2 font-weight-medium">Export CSV</span>
      <v-spacer />
      <span class="caption grey--text text--darken-1">
        {{ selection_label }}
      </span>
    </div>

    <div class="d-flex align-center mb-2">
      <v-btn
        v-tooltip="'Include every channel in the export'"
        small
        text
        class="mr-1"
        :disabled="Boolean(export_progress)"
        @click="selectAll"
      >
        Select all
      </v-btn>
      <v-btn
        v-tooltip="'Clear the channel selection'"
        small
        text
        :disabled="Boolean(export_progress)"
        @click="selectNone"
      >
        Clear
      </v-btn>
      <v-btn
        v-tooltip="'Select every channel except video and raw byte streams'"
        small
        text
        :disabled="Boolean(export_progress)"
        @click="selectDefaults"
      >
        Default
      </v-btn>
    </div>

    <v-data-table
      v-model="selected"
      :headers="headers"
      :items="channels"
      item-key="channelId"
      show-select
      dense
      :items-per-page="8"
      class="channel-table elevation-0"
      :loading="channels.length === 0"
      :footer-props="{ 'items-per-page-options': [8, 16, -1] }"
    >
      <template #item.schemaName="{ item }">
        <span class="text-truncate d-inline-block channel-schema">
          {{ item.schemaName || '-' }}
        </span>
      </template>
      <template #item.messageCount="{ item }">
        {{ item.messageCount.toLocaleString() }}
      </template>
    </v-data-table>

    <div class="d-flex align-center mt-3">
      <template v-if="export_progress">
        <div class="export-progress flex-grow-1 mr-3">
          <div class="d-flex align-center caption mb-1">
            <span>{{ export_status }}</span>
            <v-spacer />
            <span>{{ export_percentage }}%</span>
          </div>
          <v-progress-linear
            :value="export_percentage"
            height="6"
            rounded
            color="primary"
          />
        </div>
        <v-btn
          small
          text
          class="mr-2"
          @click="cancelExport"
        >
          Cancel
        </v-btn>
      </template>
      <v-spacer v-else />
      <v-btn
        small
        color="primary"
        :loading="Boolean(export_progress)"
        :disabled="Boolean(export_progress) || selected.length === 0"
        @click="saveCsv"
      >
        <v-icon small left>
          mdi-download
        </v-icon>
        Save as CSV
      </v-btn>
    </div>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import {
  CsvExportProgress,
  defaultSelectedChannelIds,
  exportChannelsAsCsv,
  McapRecordingChannel,
} from '@/libs/mcap/csv'
import { Mp4ExportRange, saveBlob } from '@/libs/mcap/export'
import { McapVideoRecording } from '@/libs/mcap/player'
import { prettifySize } from '@/utils/helper_functions'

const PROGRESS_INTERVAL_MS = 200

export default Vue.extend({
  name: 'McapCsvExport',
  props: {
    recording: {
      type: Object as PropType<McapVideoRecording>,
      required: true,
    },
    clip: {
      type: Object as PropType<Mp4ExportRange | null>,
      default: null,
    },
    name: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      selected: [] as McapRecordingChannel[],
      export_progress: null as CsvExportProgress | null,
      export_controller: null as AbortController | null,
      last_progress_at: 0,
    }
  },
  computed: {
    channels(): McapRecordingChannel[] {
      return this.recording.channels
    },
    headers(): { text: string, value: string }[] {
      return [
        { text: 'Topic', value: 'topic' },
        { text: 'Schema', value: 'schemaName' },
        { text: 'Encoding', value: 'messageEncoding' },
        { text: 'Messages', value: 'messageCount' },
      ]
    },
    selection_label(): string {
      if (this.selected.length === 0) {
        return 'No channels selected'
      }
      if (this.selected.length === this.channels.length) {
        return `All ${this.channels.length} channels`
      }
      return `${this.selected.length} of ${this.channels.length} channels`
    },
    export_percentage(): number {
      const { seconds, durationSeconds } = this.export_progress ?? { seconds: 0, durationSeconds: 0 }
      if (durationSeconds <= 0) {
        return 0
      }
      return Math.min(100, Math.round(seconds / durationSeconds * 100))
    },
    export_status(): string {
      const size = prettifySize((this.export_progress?.bytes ?? 0) / 1024)
      const messages = this.export_progress?.messages ?? 0
      return `Saving CSV · ${messages.toLocaleString()} messages · ${size}`
    },
  },
  mounted() {
    this.selectDefaults()
  },
  beforeDestroy() {
    this.export_controller?.abort()
  },
  methods: {
    selectAll(): void {
      this.selected = [...this.channels]
    },
    selectNone(): void {
      this.selected = []
    },
    selectDefaults(): void {
      const ids = new Set(defaultSelectedChannelIds(this.channels))
      this.selected = this.channels.filter((channel) => ids.has(channel.channelId))
    },
    fileName(): string {
      const { clip } = this
      if (!clip) {
        return `${this.name}.csv`
      }
      const end = Number.isFinite(clip.endSeconds) ? `${Math.round(clip.endSeconds)}s` : 'end'
      return `${this.name}-${Math.round(clip.startSeconds)}s-${end}.csv`
    },
    async saveCsv(): Promise<void> {
      if (this.export_progress || this.selected.length === 0) {
        return
      }
      const controller = new AbortController()
      const { clip } = this
      const end = Math.min(clip?.endSeconds ?? Infinity, this.recording.durationSeconds)
      const durationSeconds = Math.max(end - (clip?.startSeconds ?? 0), 0)
      this.export_controller = controller
      this.export_progress = {
        seconds: 0, durationSeconds, bytes: 0, messages: 0,
      }
      try {
        const file = await exportChannelsAsCsv(
          this.recording,
          this.selected.map((channel) => channel.channelId),
          {
            range: clip ?? undefined,
            signal: controller.signal,
            onProgress: (progress) => {
              const now = Date.now()
              if (now - this.last_progress_at >= PROGRESS_INTERVAL_MS) {
                this.last_progress_at = now
                this.export_progress = progress
              }
            },
          },
        )
        saveBlob(file, this.fileName())
      } catch (error) {
        if (!(error instanceof Error) || error.name !== 'AbortError') {
          this.$emit('error', error instanceof Error ? error.message : String(error))
        }
      } finally {
        this.export_controller = null
        this.export_progress = null
      }
    },
    cancelExport(): void {
      this.export_controller?.abort()
    },
  },
})
</script>

<style scoped>
.csv-export {
  border-top: 1px solid rgba(128, 128, 128, 0.35);
}

.channel-table {
  background: transparent;
}

.channel-schema {
  max-width: 220px;
}

.export-progress {
  min-width: 0;
}
</style>
