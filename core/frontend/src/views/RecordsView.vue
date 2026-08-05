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
          <div class="preview-wrapper">
            <div class="processing-preview grey lighten-3 d-flex flex-column align-center justify-center">
              <v-progress-circular
                indeterminate
                color="primary"
                size="48"
              />
              <span class="mt-2 caption grey--text text--darken-1">
                Repairing recording index...
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
              Repairing
            </v-chip>
          </v-card-subtitle>
          <v-spacer />
        </v-card>
      </v-col>
      <v-col
        v-for="file in visibleRecordings"
        :key="file.path"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card class="record-card d-flex flex-column">
          <div class="preview-wrapper">
            <div
              class="record-preview grey darken-3 d-flex flex-column align-center justify-center preview-clickable"
              role="button"
              tabindex="0"
              @click="openPlayer(file)"
              @keydown.enter="openPlayer(file)"
            >
              <img
                v-if="thumbnailUrl(file)"
                :src="thumbnailUrl(file)"
                class="preview-image"
                alt=""
              >
              <div class="preview-overlay d-flex flex-column align-center justify-center">
                <v-btn icon large color="primary" class="play-btn">
                  <v-icon large>
                    mdi-play-circle
                  </v-icon>
                </v-btn>
                <div class="mt-2 caption text-center preview-caption">
                  <div v-if="summaryOf(file)">
                    {{ formatDuration(summaryOf(file).durationSeconds) }}
                    &middot;
                    {{ streamsLabel(summaryOf(file)) }}
                  </div>
                  <template v-else-if="summaryError(file)">
                    <div>{{ repairFailure(file) ?? summaryError(file) }}</div>
                    <v-btn
                      v-if="needsRepair(file)"
                      v-tooltip="'Rewrite this recording on the vehicle so that it can be read'"
                      x-small
                      text
                      color="primary"
                      class="mt-1"
                      @click.stop="repair(file)"
                    >
                      <v-icon x-small left>
                        mdi-wrench
                      </v-icon>
                      Repair
                    </v-btn>
                  </template>
                  <v-progress-circular v-else indeterminate size="14" width="2" color="grey" />
                </div>
              </div>
            </div>
          </div>
          <v-card-title class="py-2">
            <div class="text-truncate" :title="file.name">
              {{ file.name }}
            </div>
          </v-card-title>
          <v-card-subtitle class="py-0">
            <v-chip x-small class="mr-2" color="primary">
              MCAP
            </v-chip>
            <span class="mr-2">{{ formatSize(file.size_bytes) }}</span>
            <span class="caption">{{ formatDate(file.modified) }}</span>
          </v-card-subtitle>
          <v-spacer />
          <v-card-actions class="pt-0">
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
        <v-card-title class="headline d-flex align-center">
          <span class="text-truncate">{{ activeRecord?.name }}</span>
          <v-spacer />
          <v-btn
            v-tooltip="'Download the recording as it was made, to open in other tools'"
            small
            text
            color="primary"
            :href="activeRecord?.download_url"
            :download="activeRecord?.name"
            @click.stop
          >
            <v-icon small left>
              mdi-download
            </v-icon>
            MCAP
          </v-btn>
          <v-btn
            v-tooltip="'Close'"
            icon
            small
            class="ml-2"
            color="primary"
            @click.stop="closePlayer"
          >
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <mcap-video-player
            v-if="activeRecord"
            :key="activeRecord.path"
            :url="activeRecord.stream_url"
          />
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import McapVideoPlayer from '@/components/records/McapVideoPlayer.vue'
import { McapVideoSummary, readMcapVideoSummary } from '@/libs/mcap/player'
import { McapNeedsRepairError } from '@/libs/mcap/reader'
import { extractMcapThumbnail } from '@/libs/mcap/thumbnail'
import { deleteCachedThumbnail, getCachedThumbnail, setCachedThumbnail } from '@/libs/mcap/thumbnail-cache'
import { OneMoreTime } from '@/one-more-time'
import records_store from '@/store/records'
import { FailedRepair, ProcessingFile, RecordingFile } from '@/types/records'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'RecordsView',
  components: {
    McapVideoPlayer,
  },
  data() {
    return {
      playerOpen: false,
      activeRecord: null as RecordingFile | null,
      summaries: {} as Record<string, McapVideoSummary>,
      summaryErrors: {} as Record<string, string>,
      repairable: {} as Record<string, boolean>,
      /** Object URLs for JPEG previews already in memory this session. */
      thumbnails: {} as Record<string, string>,
      thumbnailFailed: {} as Record<string, boolean>,
      thumbnailController: null as AbortController | null,
      statusPoller: null as OneMoreTime | null,
    }
  },
  computed: {
    recordings(): RecordingFile[] {
      return records_store.recordings
    },
    /** A recording being repaired is shown by its own card, so it is left out of this list. */
    visibleRecordings(): RecordingFile[] {
      const beingRepaired = this.processingFiles.map((file) => file.path)
      return this.recordings.filter((file) => !beingRepaired.includes(file.path))
    },
    processingFiles(): ProcessingFile[] {
      return records_store.processing_files
    },
    failedRepairs(): FailedRepair[] {
      return records_store.failed_repairs
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
        const repairing = this.processingFiles.map((file) => file.path)
        await records_store.fetchProcessingStatus()
        const stillRepairing = this.processingFiles.map((file) => file.path)
        const finished = repairing.filter((path) => !stillRepairing.includes(path))
        if (finished.length === 0) {
          return
        }
        // A repaired recording is a different file, so whatever was read out of it no longer holds
        finished.forEach((path) => this.forgetSummary(path))
        await records_store.fetchRecordings()
        await this.loadSummaries()
      },
    )
  },
  beforeDestroy() {
    this.thumbnailController?.abort()
    Object.values(this.thumbnails).forEach((url) => URL.revokeObjectURL(url))
  },
  methods: {
    async refresh(): Promise<void> {
      await Promise.all([
        records_store.fetchRecordings(),
        records_store.fetchProcessingStatus(),
      ])
      await this.loadSummaries()
    },
    /**
     * Reads what each recording contains directly from its index. Recordings are read one at a time
     * to leave the link to the vehicle free for playback.
     */
    async loadSummaries(): Promise<void> {
      const pending = this.recordings.filter(
        (file) => !this.summaries[file.path] && !this.summaryErrors[file.path],
      )
      for (const file of pending) {
        try {
          // eslint-disable-next-line no-await-in-loop
          this.$set(this.summaries, file.path, await readMcapVideoSummary(file.stream_url))
        } catch (error) {
          this.$set(this.summaryErrors, file.path, error instanceof Error ? error.message : String(error))
          this.$set(this.repairable, file.path, error instanceof McapNeedsRepairError)
        }
      }
      await this.loadThumbnails()
    },
    /**
     * Builds JPEG previews one recording at a time. Stops while the player is open so seeking and
     * playback keep the link to themselves.
     */
    async loadThumbnails(): Promise<void> {
      const pending = this.recordings.filter((file) => {
        if (this.thumbnails[file.path] || this.thumbnailFailed[file.path] || this.summaryErrors[file.path]) {
          return false
        }
        const summary = this.summaries[file.path]
        return Boolean(summary?.tracks.some((track) => track.frameCount > 0))
      })
      for (const file of pending) {
        if (this.playerOpen) {
          return
        }
        // eslint-disable-next-line no-await-in-loop
        await this.loadThumbnail(file)
      }
    },
    async loadThumbnail(file: RecordingFile): Promise<void> {
      const cacheKey = {
        path: file.path,
        sizeBytes: file.size_bytes,
        modified: file.modified,
      }
      const cached = await getCachedThumbnail(cacheKey)
      if (cached) {
        this.rememberThumbnail(file.path, cached)
        return
      }

      this.thumbnailController?.abort()
      const controller = new AbortController()
      this.thumbnailController = controller
      try {
        const blob = await extractMcapThumbnail(file.stream_url, { signal: controller.signal })
        if (!blob || controller.signal.aborted) {
          if (!blob) {
            this.$set(this.thumbnailFailed, file.path, true)
          }
          return
        }
        await setCachedThumbnail(cacheKey, blob)
        this.rememberThumbnail(file.path, blob)
      } catch (error) {
        if (controller.signal.aborted) {
          return
        }
        this.$set(this.thumbnailFailed, file.path, true)
        console.warn(`Failed to build a preview for ${file.name}:`, error)
      } finally {
        if (this.thumbnailController === controller) {
          this.thumbnailController = null
        }
      }
    },
    rememberThumbnail(path: string, blob: Blob): void {
      const previous = this.thumbnails[path]
      if (previous) {
        URL.revokeObjectURL(previous)
      }
      this.$set(this.thumbnails, path, URL.createObjectURL(blob))
    },
    forgetThumbnail(path: string): void {
      const url = this.thumbnails[path]
      if (url) {
        URL.revokeObjectURL(url)
      }
      this.$delete(this.thumbnails, path)
      this.$delete(this.thumbnailFailed, path)
    },
    forgetSummary(path: string): void {
      const file = this.recordings.find((recording) => recording.path === path)
      if (file) {
        deleteCachedThumbnail({
          path: file.path,
          sizeBytes: file.size_bytes,
          modified: file.modified,
        }).catch(() => undefined)
      }
      this.forgetThumbnail(path)
      this.$delete(this.summaries, path)
      this.$delete(this.summaryErrors, path)
      this.$delete(this.repairable, path)
    },
    thumbnailUrl(file: RecordingFile): string | null {
      return this.thumbnails[file.path] ?? null
    },
    summaryOf(file: RecordingFile): McapVideoSummary | null {
      return this.summaries[file.path] ?? null
    },
    summaryError(file: RecordingFile): string | null {
      return this.summaryErrors[file.path] ?? null
    },
    needsRepair(file: RecordingFile): boolean {
      return this.repairable[file.path] ?? false
    },
    repairFailure(file: RecordingFile): string | null {
      return this.failedRepairs.find((failure) => failure.path === file.path)?.error ?? null
    },
    async repair(file: RecordingFile): Promise<void> {
      await records_store.repairRecording(file)
    },
    streamsLabel(summary: McapVideoSummary): string {
      if (summary.tracks.length === 0) {
        return 'no video'
      }
      return summary.tracks.map((track) => track.name).join(', ')
    },
    formatDuration(seconds: number): string {
      const total = Math.round(seconds)
      const minutes = Math.floor(total / 60)
      return `${minutes}m ${String(total % 60).padStart(2, '0')}s`
    },
    async deleteRecording(file: RecordingFile): Promise<void> {
      await deleteCachedThumbnail({
        path: file.path,
        sizeBytes: file.size_bytes,
        modified: file.modified,
      })
      this.forgetThumbnail(file.path)
      await records_store.deleteRecording(file)
    },
    openPlayer(file: RecordingFile): void {
      this.thumbnailController?.abort()
      this.activeRecord = file
      this.playerOpen = true
    },
    closePlayer(): void {
      this.playerOpen = false
      this.loadThumbnails()
    },
    formatSize(bytes: number): string {
      return prettifySize(bytes / 1024)
    },
    formatDate(timestamp: number): string {
      const date = new Date(timestamp * 1000)
      return date.toLocaleString()
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

.preview-wrapper {
  position: relative;
}

.record-preview {
  position: relative;
  overflow: hidden;
}

.preview-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-overlay {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  padding: 8px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0.15));
}

.preview-caption {
  color: rgba(255, 255, 255, 0.9);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
}

.play-btn {
  background-color: rgba(255, 255, 255, 0.85) !important;
  pointer-events: all;
}

.preview-clickable {
  cursor: pointer;
}

.player-card {
  position: relative;
}

.mr-2 {
  margin-right: 8px;
}

.processing-card {
  opacity: 0.85;
}

.processing-preview,
.record-preview {
  height: 180px;
}
</style>
