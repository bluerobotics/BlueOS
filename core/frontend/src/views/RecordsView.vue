<template>
  <v-container fluid class="records-view">
    <v-overlay
      v-if="!isSafe"
      absolute
      :opacity="0.9"
      z-index="10"
    >
      <div class="d-flex flex-column align-center text-center pa-4">
        <v-icon large color="warning" class="mb-3">
          mdi-alert-outline
        </v-icon>
        <p class="mb-0">
          Recording browsing is paused while the vehicle is armed,
          so the link stays free for vehicle control.
        </p>
      </div>
    </v-overlay>

    <v-alert
      v-if="error"
      type="error"
      dense
      class="mb-4"
    >
      {{ error }}
    </v-alert>

    <v-alert
      v-else-if="!loading && recordings.length === 0"
      type="info"
      dense
      class="mb-4"
    >
      No recordings found yet.
    </v-alert>

    <v-select
      v-if="dateFilterOptions.length > 1"
      v-model="selectedDate"
      :items="dateFilterOptions"
      label="Filter by date (UTC)"
      dense
      outlined
      hide-details
      class="mb-4 date-filter"
    />

    <v-row>
      <v-col
        v-for="file in filteredRecordings"
        :key="file.path"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card class="record-card d-flex flex-column">
          <div class="preview-wrapper">
            <div
              class="record-preview grey darken-3 d-flex flex-column align-center justify-center"
              :class="{ 'preview-clickable': canPlay(file) }"
              :role="canPlay(file) ? 'button' : undefined"
              :tabindex="canPlay(file) ? 0 : undefined"
              @click="canPlay(file) && openPlayer(file)"
              @keydown.enter="canPlay(file) && openPlayer(file)"
            >
              <img
                v-if="thumbnailUrl(file)"
                :src="thumbnailUrl(file)"
                class="preview-image"
                alt=""
              >
              <div class="preview-overlay d-flex flex-column align-center justify-center">
                <v-btn
                  v-if="canPlay(file)"
                  icon
                  large
                  color="primary"
                  class="play-btn"
                >
                  <v-icon large>
                    mdi-play-circle
                  </v-icon>
                </v-btn>
                <v-progress-circular
                  v-else-if="file.state === 'repairing'"
                  indeterminate
                  color="primary"
                  size="48"
                />
                <v-icon
                  v-else-if="file.state === 'recording'"
                  large
                  color="warning"
                >
                  mdi-record-circle
                </v-icon>
                <v-icon
                  v-else-if="file.state === 'needs_repair'"
                  large
                  color="error"
                >
                  mdi-alert-circle-outline
                </v-icon>
                <div class="mt-2 caption text-center preview-caption">
                  <div v-if="durationLabel(file)">
                    {{ durationLabel(file) }}
                  </div>
                  <div v-if="file.state === 'recording'">
                    recording…
                  </div>
                  <div v-else-if="endedLabel(file)">
                    ended {{ endedLabel(file) }}
                  </div>
                  <template v-if="file.state === 'needs_repair'">
                    <div>{{ repairFailure(file) ?? 'Recording index is missing' }}</div>
                    <v-btn
                      v-tooltip="'Rewrite this recording on the vehicle so that it can be read'"
                      x-small
                      text
                      color="primary"
                      class="mt-1"
                      :disabled="!canRepair(file)"
                      @click.stop="repair(file)"
                    >
                      <v-icon x-small left>
                        mdi-wrench
                      </v-icon>
                      Repair
                    </v-btn>
                  </template>
                  <div v-else-if="file.state === 'repairing'">
                    Repairing recording index…
                  </div>
                </div>
              </div>
            </div>
          </div>
          <v-card-title class="py-2">
            <div class="text-truncate">
              {{ file.name }}
            </div>
          </v-card-title>
          <v-card-subtitle class="py-0">
            <v-chip
              x-small
              class="mr-2"
              :color="stateChipColor(file.state)"
            >
              {{ stateChipLabel(file.state) }}
            </v-chip>
            <span class="mr-2">{{ formatSize(file.size_bytes) }}</span>
            <span class="caption">{{ formatDate(file.created) }}</span>
          </v-card-subtitle>
          <v-card-subtitle v-if="tracksLabel(file)" class="py-0 caption">
            {{ tracksLabel(file) }}
          </v-card-subtitle>
          <v-spacer />
          <v-card-actions class="pt-0">
            <span v-tooltip="deleteTooltip(file)">
              <v-btn
                icon
                small
                color="error"
                :disabled="!canDelete(file)"
                @click="deleteRecording(file)"
              >
                <v-icon>mdi-delete</v-icon>
              </v-btn>
            </span>
            <v-btn
              v-if="file.state === 'needs_repair'"
              v-tooltip="'Rewrite this recording on the vehicle so that it can be read'"
              icon
              small
              color="primary"
              :disabled="!canRepair(file)"
              @click="repair(file)"
            >
              <v-icon>mdi-wrench</v-icon>
            </v-btn>
            <v-spacer />
            <span v-tooltip="downloadTooltip(file)">
              <v-btn
                icon
                small
                color="primary"
                :disabled="!canDownload(file)"
                :loading="downloadingPaths[file.path]"
                @click="downloadRecording(file)"
              >
                <v-icon>mdi-download</v-icon>
              </v-btn>
            </span>
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
        <v-card-title class="headline d-flex align-center flex-wrap">
          <div class="text-truncate mr-2">
            {{ activeRecord?.name }}
          </div>
          <span
            v-if="activeRecordMeta"
            class="caption grey--text text--darken-1 font-weight-regular mr-2"
          >
            {{ activeRecordMeta }}
          </span>
          <v-spacer />
          <v-btn
            v-tooltip="'Download the recording as it was made, to open in other tools'"
            small
            text
            color="primary"
            :disabled="!activeRecord || !canDownload(activeRecord)"
            @click.stop="activeRecord && downloadRecording(activeRecord)"
          >
            <v-icon small left>
              mdi-download
            </v-icon>
            Download MCAP
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
import { extractMcapThumbnail } from '@/libs/mcap/thumbnail'
import { deleteCachedThumbnail, getCachedThumbnail, setCachedThumbnail } from '@/libs/mcap/thumbnail-cache'
import { OneMoreTime } from '@/one-more-time'
import autopilot_data from '@/store/autopilot'
import records_store from '@/store/records'
import { RecordingFile, RecordingState } from '@/types/records'
import { prettifySize } from '@/utils/helper_functions'

const ALL_DATES = ''
const SPLIT_READY_TIMEOUT_MS = 5 * 60 * 1000
const SPLIT_READY_POLL_MS = 2000

function utcCalendarDay(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatUtcDayLabel(day: string): string {
  const [year, month, date] = day.split('-')
  return `${year}-${month}-${date} UTC`
}

export default Vue.extend({
  name: 'RecordsView',
  components: {
    McapVideoPlayer,
  },
  data() {
    return {
      playerOpen: false,
      activeRecord: null as RecordingFile | null,
      selectedDate: ALL_DATES,
      summaries: {} as Record<string, McapVideoSummary>,
      thumbnails: {} as Record<string, string>,
      thumbnailFailed: {} as Record<string, boolean>,
      thumbnailController: null as AbortController | null,
      summaryController: null as AbortController | null,
      downloadingPaths: {} as Record<string, boolean>,
      statusPoller: null as OneMoreTime | null,
    }
  },
  computed: {
    isSafe(): boolean {
      return autopilot_data.is_safe
    },
    recordings(): RecordingFile[] {
      return records_store.recordings
    },
    failedRepairs() {
      return records_store.failed_repairs
    },
    loading(): boolean {
      return records_store.loading
    },
    error(): string | null {
      return records_store.error
    },
    dateFilterOptions(): { text: string, value: string }[] {
      const days = new Set(this.recordings.map((file) => utcCalendarDay(file.created)))
      const sorted = Array.from(days).sort((left, right) => right.localeCompare(left))
      return [
        { text: 'All dates', value: ALL_DATES },
        ...sorted.map((day) => ({ text: formatUtcDayLabel(day), value: day })),
      ]
    },
    filteredRecordings(): RecordingFile[] {
      if (!this.selectedDate) {
        return this.recordings
      }
      return this.recordings.filter((file) => utcCalendarDay(file.created) === this.selectedDate)
    },
    activeRecordMeta(): string | null {
      const file = this.activeRecord
      if (!file) {
        return null
      }
      const parts: string[] = []
      const duration = this.durationSeconds(file)
      if (duration !== null) {
        parts.push(this.formatDuration(duration))
      }
      const summary = this.summaries[file.path]
      if (summary && summary.tracks.length > 0) {
        parts.push(`${summary.tracks.length} stream${summary.tracks.length === 1 ? '' : 's'}`)
      }
      parts.push(this.formatSize(file.size_bytes))
      return parts.join(' · ')
    },
    needsPolling(): boolean {
      return this.recordings.some(
        (file) => file.state === 'recording' || file.state === 'repairing',
      )
    },
  },
  watch: {
    isSafe(safe: boolean) {
      if (safe) {
        this.refresh()
        this.syncStatusPoller(this.needsPolling)
        return
      }
      this.pauseNetworkActivity()
      this.syncStatusPoller(false)
    },
    needsPolling(active: boolean) {
      this.syncStatusPoller(active)
    },
  },
  mounted() {
    if (this.isSafe) {
      this.refresh()
    }
    this.statusPoller = new OneMoreTime(
      { delay: 5000, disposeWith: this, autostart: false },
      async () => {
        if (!this.isSafe || !this.needsPolling) {
          return
        }
        await records_store.fetchRecordings()
        if (!this.isSafe) {
          return
        }
        await records_store.fetchProcessingStatus()
        await this.loadSummaries()
      },
    )
    this.syncStatusPoller(this.needsPolling)
  },
  beforeDestroy() {
    this.pauseNetworkActivity()
    Object.values(this.thumbnails).forEach((url) => URL.revokeObjectURL(url))
  },
  methods: {
    syncStatusPoller(active: boolean): void {
      const poller = this.statusPoller as (OneMoreTime & {
        isPaused?: boolean
        isRunning?: boolean
        timeoutId?: ReturnType<typeof setTimeout>
      }) | null
      if (!poller) {
        return
      }
      if (active && this.isSafe) {
        if (poller.isPaused) {
          poller.resume()
        } else if (!poller.isRunning && !poller.timeoutId) {
          poller.start()
        }
      } else {
        poller.stop()
      }
    },
    pauseNetworkActivity(): void {
      this.thumbnailController?.abort()
      this.thumbnailController = null
      this.summaryController?.abort()
      this.summaryController = null
      if (this.playerOpen) {
        this.playerOpen = false
        this.activeRecord = null
      }
    },
    async refresh(): Promise<void> {
      if (!this.isSafe) {
        return
      }
      await Promise.all([
        records_store.fetchRecordings(),
        records_store.fetchProcessingStatus(),
      ])
      if (!this.isSafe) {
        return
      }
      await this.loadSummaries()
    },
    readyFiles(): RecordingFile[] {
      return this.recordings.filter((file) => file.state === 'ready')
    },
    async loadSummaries(): Promise<void> {
      if (!this.isSafe) {
        return
      }
      this.summaryController?.abort()
      const controller = new AbortController()
      this.summaryController = controller
      const pending = this.readyFiles().filter(
        (file) => !this.summaries[file.path],
      )
      try {
        for (const file of pending) {
          if (!this.isSafe || controller.signal.aborted) {
            return
          }
          try {
            // eslint-disable-next-line no-await-in-loop
            this.$set(
              this.summaries,
              file.path,
              await readMcapVideoSummary(file.stream_url, controller.signal),
            )
          } catch (error) {
            if (controller.signal.aborted || !this.isSafe) {
              return
            }
            console.warn(`Failed to read video summary for ${file.name}:`, error)
          }
        }
      } finally {
        if (this.summaryController === controller) {
          this.summaryController = null
        }
      }
      await this.loadThumbnails()
    },
    async loadThumbnails(): Promise<void> {
      if (!this.isSafe) {
        return
      }
      const pending = this.readyFiles().filter((file) => {
        if (this.thumbnails[file.path] || this.thumbnailFailed[file.path]) {
          return false
        }
        const summary = this.summaries[file.path]
        return Boolean(summary?.tracks.some((track) => track.frameCount > 0))
      })
      for (const file of pending) {
        if (!this.isSafe || this.playerOpen) {
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
        modified: file.created,
      }
      const cached = await getCachedThumbnail(cacheKey)
      if (cached) {
        this.rememberThumbnail(file.path, cached)
        return
      }
      if (!this.isSafe) {
        return
      }

      this.thumbnailController?.abort()
      const controller = new AbortController()
      this.thumbnailController = controller
      try {
        const blob = await extractMcapThumbnail(file.stream_url, { signal: controller.signal })
        if (!blob || controller.signal.aborted || !this.isSafe) {
          if (!blob && this.isSafe) {
            this.$set(this.thumbnailFailed, file.path, true)
          }
          return
        }
        await setCachedThumbnail(cacheKey, blob)
        this.rememberThumbnail(file.path, blob)
      } catch (error) {
        if (controller.signal.aborted || !this.isSafe) {
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
          modified: file.created,
        }).catch(() => undefined)
      }
      this.forgetThumbnail(path)
      this.$delete(this.summaries, path)
    },
    thumbnailUrl(file: RecordingFile): string | null {
      return this.thumbnails[file.path] ?? null
    },
    repairFailure(file: RecordingFile): string | null {
      return this.failedRepairs.find((failure) => failure.path === file.path)?.error ?? null
    },
    canPlay(file: RecordingFile): boolean {
      return file.state === 'ready'
    },
    canDelete(file: RecordingFile): boolean {
      return this.isSafe && file.state !== 'recording' && file.state !== 'repairing'
    },
    canRepair(file: RecordingFile): boolean {
      return this.isSafe && file.state === 'needs_repair'
    },
    canDownload(file: RecordingFile): boolean {
      if (!this.isSafe || this.downloadingPaths[file.path]) {
        return false
      }
      return file.state === 'ready' || file.state === 'recording'
    },
    deleteTooltip(file: RecordingFile): string {
      if (file.state === 'recording') {
        return 'Cannot delete while the vehicle is still recording'
      }
      if (file.state === 'repairing') {
        return 'Cannot delete while the recording is being repaired'
      }
      return `Delete ${file.name}`
    },
    downloadTooltip(file: RecordingFile): string {
      if (file.state === 'needs_repair') {
        return 'Repair the recording before downloading'
      }
      if (file.state === 'repairing') {
        return 'Wait until repair finishes before downloading'
      }
      if (file.state === 'recording') {
        return 'Download a snapshot copy of the live recording'
      }
      return `Download ${file.name}`
    },
    stateChipColor(state: RecordingState): string {
      const colors: Record<RecordingState, string> = {
        recording: 'warning',
        needs_repair: 'error',
        repairing: 'primary',
        ready: 'success',
      }
      return colors[state]
    },
    stateChipLabel(state: RecordingState): string {
      const labels: Record<RecordingState, string> = {
        recording: 'Recording',
        needs_repair: 'Needs repair',
        repairing: 'Repairing',
        ready: 'Ready',
      }
      return labels[state]
    },
    durationSeconds(file: RecordingFile): number | null {
      if (file.state === 'recording') {
        return Math.max(0, Date.now() / 1000 - file.created)
      }
      const summary = this.summaries[file.path]
      if (!summary) {
        return null
      }
      return summary.durationSeconds
    },
    durationLabel(file: RecordingFile): string | null {
      const duration = this.durationSeconds(file)
      if (duration === null) {
        return null
      }
      return this.formatDuration(duration)
    },
    endedLabel(file: RecordingFile): string | null {
      const summary = this.summaries[file.path]
      if (!summary) {
        return null
      }
      return this.formatDate(summary.ended)
    },
    tracksLabel(file: RecordingFile): string | null {
      const summary = this.summaries[file.path]
      if (!summary) {
        return null
      }
      const videoNames = summary.tracks.map((track) => track.name)
      const otherCount = summary.channels.length - summary.tracks.length
      if (videoNames.length === 0 && otherCount === 0) {
        return 'no topics'
      }
      const parts: string[] = []
      if (videoNames.length > 0) {
        parts.push(videoNames.join(', '))
      }
      if (otherCount > 0) {
        parts.push(`${otherCount} other topic${otherCount === 1 ? '' : 's'}`)
      }
      return parts.join(' · ')
    },
    async repair(file: RecordingFile): Promise<void> {
      if (!this.canRepair(file)) {
        return
      }
      await records_store.repairRecording(file)
      await records_store.fetchRecordings()
      this.syncStatusPoller(this.needsPolling)
    },
    async downloadRecording(file: RecordingFile): Promise<void> {
      if (!this.canDownload(file)) {
        return
      }
      if (file.state === 'ready') {
        this.triggerDownload(file.download_url, file.name)
        return
      }
      this.$set(this.downloadingPaths, file.path, true)
      records_store.setError(null)
      try {
        const response = await records_store.splitRecording(file)
        if (!response || !this.isSafe) {
          return
        }
        const readyFile = await this.waitForRecordingReady(response.recording.path)
        if (readyFile) {
          this.triggerDownload(readyFile.download_url, readyFile.name)
        }
      } finally {
        this.$delete(this.downloadingPaths, file.path)
      }
    },
    async waitForRecordingReady(path: string): Promise<RecordingFile | null> {
      const deadline = Date.now() + SPLIT_READY_TIMEOUT_MS
      while (Date.now() < deadline) {
        if (!this.isSafe) {
          return null
        }
        await records_store.fetchRecordings()
        await records_store.fetchProcessingStatus()
        const file = records_store.recordings.find((recording) => recording.path === path)
        if (file?.state === 'ready') {
          return file
        }
        const failed = records_store.failed_repairs.find((failure) => failure.path === path)
        if (failed) {
          records_store.setError(`Could not prepare download: ${failed.error}`)
          return null
        }
        if (file?.state === 'needs_repair') {
          records_store.setError('Could not prepare download: the split recording needs repair.')
          return null
        }
        const stillProcessing = records_store.processing_files.some((processing) => processing.path === path)
        if (!file && !stillProcessing) {
          records_store.setError('Could not prepare download: the split recording is no longer available.')
          return null
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise<void>((resolve) => {
          setTimeout(resolve, SPLIT_READY_POLL_MS)
        })
      }
      records_store.setError('Timed out while preparing the recording download.')
      return null
    },
    triggerDownload(url: string, filename: string): void {
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
    },
    formatDuration(seconds: number): string {
      const total = Math.round(seconds)
      const minutes = Math.floor(total / 60)
      return `${minutes}m ${String(total % 60).padStart(2, '0')}s`
    },
    async deleteRecording(file: RecordingFile): Promise<void> {
      if (!this.canDelete(file)) {
        return
      }
      await deleteCachedThumbnail({
        path: file.path,
        sizeBytes: file.size_bytes,
        modified: file.created,
      })
      this.forgetThumbnail(file.path)
      this.forgetSummary(file.path)
      await records_store.deleteRecording(file)
    },
    openPlayer(file: RecordingFile): void {
      if (!this.canPlay(file) || !this.isSafe) {
        return
      }
      this.thumbnailController?.abort()
      this.activeRecord = file
      this.playerOpen = true
    },
    closePlayer(): void {
      this.playerOpen = false
      this.activeRecord = null
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
  position: relative;
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
  height: 180px;
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

.date-filter {
  max-width: 280px;
}

.mr-2 {
  margin-right: 8px;
}
</style>
