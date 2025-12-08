<template>
  <v-container fluid class="records-view">
    <v-alert
      v-if="error"
      type="error"
      dense
      class="mb-4"
    >
      {{ error }}
    </v-alert>

    <v-alert
      v-else-if="!loading && recordings.length === 0 && processingFiles.length === 0"
      type="info"
      dense
      class="mb-4"
    >
      No recordings found yet.
    </v-alert>

    <v-row>
      <v-col
        v-for="processing in processingFiles"
        :key="`processing-${processing.path}`"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card class="record-card d-flex flex-column processing-card">
          <div class="thumbnail-wrapper">
            <div class="processing-thumbnail grey lighten-3 d-flex flex-column align-center justify-center">
              <v-progress-circular
                indeterminate
                color="primary"
                size="48"
              />
              <span class="mt-2 caption grey--text text--darken-1">
                Extracting video...
              </span>
            </div>
          </div>
          <v-card-title class="py-2">
            <div class="text-truncate" :title="processing.name">
              {{ processing.name }}
            </div>
          </v-card-title>
          <v-card-subtitle class="py-0">
            <v-chip x-small color="primary">
              Processing
            </v-chip>
          </v-card-subtitle>
          <v-spacer />
        </v-card>
      </v-col>
      <v-col
        v-for="file in recordings"
        :key="file.path"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card class="record-card d-flex flex-column">
          <div class="thumbnail-wrapper">
            <v-img
              :src="thumbnailSrc(file)"
              height="180"
              class="grey lighten-3 thumbnail-clickable"
              aspect-ratio="16/9"
              contain
              @error="onThumbnailError(file.path)"
              @load="onThumbnailLoad(file.path)"
              @click="openPlayer(file)"
            >
              <div v-if="brokenThumbnails[file.path]" class="fallback-icon d-flex align-center justify-center">
                <v-icon large color="grey darken-1">
                  mdi-multimedia
                </v-icon>
              </div>

              <div v-if="!isThumbnailLoading(file.path)" class="thumbnail-actions">
                <v-btn
                  icon
                  large
                  color="primary"
                  class="play-btn"
                  @click.stop="openPlayer(file)"
                >
                  <v-icon large>
                    mdi-play-circle
                  </v-icon>
                </v-btn>
              </div>
            </v-img>
            <div
              v-if="isThumbnailLoading(file.path)"
              class="thumbnail-loading grey lighten-3 d-flex flex-column align-center justify-center"
            >
              <v-progress-circular
                indeterminate
                color="primary"
                size="48"
              />
              <span class="mt-2 caption grey--text text--darken-1">
                Processing video/thumbnail...
              </span>
            </div>
          </div>
          <v-card-title class="py-2">
            <div class="text-truncate" :title="file.name">
              {{ file.name }}
            </div>
          </v-card-title>
          <v-card-subtitle class="py-0">
            <span class="mr-2">{{ formatSize(file.size_bytes) }}</span>
            <span class="caption">{{ formatDate(file.modified) }}</span>
          </v-card-subtitle>
          <v-spacer />
          <v-card-actions v-if="!isThumbnailLoading(file.path)" class="pt-0">
            <v-btn
              icon
              small
              color="error"
              :title="`Delete ${file.name}`"
              @click="deleteRecording(file)"
            >
              <v-icon>mdi-delete</v-icon>
            </v-btn>
            <v-spacer />
            <v-btn
              icon
              small
              color="primary"
              :title="`Download ${file.name}`"
              :href="file.download_url"
              :download="file.name"
              @click.stop
            >
              <v-icon>mdi-download</v-icon>
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>

    <v-dialog
      v-model="playerOpen"
      max-width="1080"
      @click:outside="closePlayer"
    >
      <v-card class="player-card">
        <v-btn
          icon
          small
          class="dialog-close"
          color="primary"
          @click.stop="closePlayer"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
        <v-card-title class="headline">
          {{ activeRecord?.name }}
        </v-card-title>
        <v-card-text>
          <div class="player-wrapper">
            <video
              v-if="activeRecord"
              ref="player"
              controls
              autoplay
              class="player"
              :src="activeRecord.stream_url"
            >
              <track
                kind="captions"
                srclang="en"
                label="Captions not available"
                :src="emptyCaptions"
                default
              />
            </video>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn
            icon
            color="primary"
            :href="activeRecord?.download_url"
            :download="activeRecord?.name"
            :title="`Download ${activeRecord?.name ?? ''}`"
            @click.stop
          >
            <v-icon>mdi-download</v-icon>
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import { OneMoreTime } from '@/one-more-time'
import records_store from '@/store/records'
import { ProcessingFile, RecordingFile } from '@/types/records'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'RecordsView',
  data() {
    return {
      playerOpen: false,
      activeRecord: null as RecordingFile | null,
      brokenThumbnails: {} as Record<string, boolean>,
      loadingThumbnails: {} as Record<string, boolean>,
      emptyCaptions: 'data:text/vtt,WEBVTT',
      statusPoller: null as OneMoreTime | null,
    }
  },
  computed: {
    recordings(): RecordingFile[] {
      return records_store.recordings
    },
    processingFiles(): ProcessingFile[] {
      return records_store.processing_files
    },
    loading(): boolean {
      return records_store.loading
    },
    error(): string | null {
      return records_store.error
    },
  },
  mounted() {
    this.refresh()
    this.statusPoller = new OneMoreTime(
      { delay: 5000, disposeWith: this },
      async () => {
        await records_store.fetchProcessingStatus()
        if (this.processingFiles.length > 0) {
          await records_store.fetchRecordings()
        }
      },
    )
  },
  methods: {
    async refresh(): Promise<void> {
      await Promise.all([
        records_store.fetchRecordings(),
        records_store.fetchProcessingStatus(),
      ])
    },
    async deleteRecording(file: RecordingFile): Promise<void> {
      await records_store.deleteRecording(file)
    },
    openPlayer(file: RecordingFile): void {
      this.activeRecord = file
      this.playerOpen = true
    },
    closePlayer(): void {
      const player = this.$refs.player as HTMLVideoElement | undefined
      if (player) {
        player.pause()
        player.currentTime = 0
      }
      this.playerOpen = false
    },
    formatSize(bytes: number): string {
      return prettifySize(bytes / 1024)
    },
    formatDate(timestamp: number): string {
      const date = new Date(timestamp * 1000)
      return date.toLocaleString()
    },
    thumbnailSrc(file: RecordingFile): string {
      return this.brokenThumbnails[file.path] ? '' : file.thumbnail_url
    },
    onThumbnailError(path: string): void {
      this.$set(this.brokenThumbnails, path, true)
      this.$set(this.loadingThumbnails, path, false)
    },
    onThumbnailLoad(path: string): void {
      this.$set(this.loadingThumbnails, path, false)
    },
    isThumbnailLoading(path: string): boolean {
      return this.loadingThumbnails[path] !== false && !this.brokenThumbnails[path]
    },
  },
})
</script>

<style scoped>
.records-view {
  min-height: 100%;
}

.record-card {
  height: 100%;
}

.thumbnail-wrapper {
  position: relative;
}

.thumbnail-actions {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.play-btn {
  background-color: rgba(255, 255, 255, 0.85) !important;
  pointer-events: all;
}

.thumbnail-clickable {
  cursor: pointer;
}

.player-card {
  position: relative;
}

.fallback-icon {
  position: absolute;
  inset: 0;
  background: #eceff1;
  pointer-events: none;
}

.dialog-close {
  position: absolute;
  top: 8px;
  right: 8px;
  z-index: 1;
}

.player-wrapper {
  position: relative;
  width: 100%;
  padding-top: 56.25%;
  background: #111827;
}

.player {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.mr-2 {
  margin-right: 8px;
}

.processing-card {
  opacity: 0.85;
}

.processing-thumbnail {
  height: 180px;
}

.thumbnail-loading {
  position: absolute;
  inset: 0;
  z-index: 1;
}
</style>
