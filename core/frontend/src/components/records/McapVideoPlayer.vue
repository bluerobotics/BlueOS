<template>
  <div class="player">
    <v-alert
      v-if="error"
      type="error"
      dense
      class="mb-2"
    >
      {{ error }}
    </v-alert>

    <div v-if="opening" class="d-flex flex-column align-center py-8">
      <v-progress-circular indeterminate color="primary" size="48" />
      <span class="mt-2 caption grey--text">Reading recording index...</span>
    </div>

    <div :class="['stream-grid', `columns-${columns}`]">
      <mcap-video-stream
        v-for="(track, index) in tracks"
        :key="track.channelId"
        :recording="recording"
        :track="track"
        :controls="index === 0"
        :statistics="statistics"
        @ready="onStreamReady(index, $event)"
        @stats="onStats(index, $event)"
      />
    </div>

    <div v-if="tracks.length > 0" class="player-footer mt-3">
      <div class="d-flex align-center caption grey--text text--darken-1 mb-2">
        <span
          v-if="bytes_downloaded > 0"
          v-tooltip="'Only the parts of the recording you watch are downloaded from the vehicle'"
        >
          {{ downloaded }} downloaded
        </span>
        <span v-if="tracks.length > 1" class="ml-3">
          {{ tracks.length }} streams sharing the same download
        </span>
        <v-spacer />
        <v-btn
          v-tooltip="statistics ? 'Hide detailed statistics' : 'Show detailed statistics'"
          small
          text
          :color="statistics ? 'primary' : undefined"
          @click="statistics = !statistics"
        >
          <v-icon small left>
            mdi-chart-box-outline
          </v-icon>
          Stats
          <v-icon small right>
            {{ statistics ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
          </v-icon>
        </v-btn>
      </div>

      <div class="export-panel pa-3">
        <div class="d-flex align-center mb-2">
          <span class="subtitle-2 font-weight-medium">Export MP4</span>
          <v-spacer />
          <span class="caption grey--text text--darken-1">
            {{ save_label }}
          </span>
        </div>

        <div class="d-flex align-center caption grey--text text--darken-1">
          <span>{{ positionLabel(0) }}</span>
          <div class="range-wrapper mx-2">
            <v-range-slider
              :value="clip_range"
              :max="duration"
              :step="clip_step"
              :min="0"
              hide-details
              dense
              thumb-label
              color="primary"
              @input="onRangeInput"
              @change="onRangeSettled"
            >
              <template #thumb-label="{ value }">
                {{ positionLabel(value) }}
              </template>
            </v-range-slider>
            <div
              :class="['playhead', $vuetify.theme.dark ? 'grey lighten-1' : 'grey darken-2']"
              :style="playhead_style"
            />
          </div>
          <span>{{ positionLabel(duration) }}</span>
        </div>

        <div class="d-flex align-center flex-wrap mt-1">
          <div class="bound-group mr-4">
            <div class="caption grey--text text--darken-1">
              Start
            </div>
            <div class="bound-value primary--text">
              {{ positionLabel(clip_range[0]) }}
            </div>
          </div>
          <div class="bound-group mr-4">
            <div class="caption grey--text text--darken-1">
              End
            </div>
            <div class="bound-value primary--text">
              {{ positionLabel(clip_range[1]) }}
            </div>
          </div>
          <div class="bound-group mr-4">
            <div class="caption grey--text text--darken-1">
              Duration
            </div>
            <div class="bound-value primary--text">
              {{ clip_duration_label }}
            </div>
          </div>
          <v-spacer />
          <v-btn
            v-tooltip="'Move the start of the saved part to the playback position'"
            small
            text
            class="mr-1"
            @click="markClipStart"
          >
            Set start to playhead
          </v-btn>
          <v-btn
            v-tooltip="'Move the end of the saved part to the playback position'"
            small
            text
            @click="markClipEnd"
          >
            Set end to playhead
          </v-btn>
        </div>

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
            :disabled="Boolean(export_progress) || tracks.length === 0"
            @click="saveMp4"
          >
            <v-icon small left>
              mdi-download
            </v-icon>
            {{ export_button_label }}
          </v-btn>
        </div>
      </div>

      <div
        v-if="leader_stats"
        class="stats-chips d-flex align-center flex-wrap caption grey--text text--darken-1 mt-2"
      >
        <span class="stats-chip mr-3">
          <v-icon x-small class="mr-1">
            mdi-image-multiple-outline
          </v-icon>
          {{ (leader_stats.framesRead ?? 0).toLocaleString() }} frames
        </span>
        <span :class="['stats-chip', 'mr-3', (leader_stats.framesLost ?? 0) > 0 ? 'warning--text' : '']">
          <v-icon x-small class="mr-1">
            mdi-alert-outline
          </v-icon>
          {{ leader_stats.framesLost ?? 0 }} lost
        </span>
        <span :class="['stats-chip', 'mr-3', (leader_stats.framesCorrupt ?? 0) > 0 ? 'error--text' : '']">
          <v-icon x-small class="mr-1">
            mdi-shield-check-outline
          </v-icon>
          {{ leader_stats.framesCorrupt ?? 0 }} corrupt
        </span>
        <span v-if="leader_stats.frameRate" class="stats-chip">
          <v-icon x-small class="mr-1">
            mdi-speedometer
          </v-icon>
          {{ leader_stats.frameRate.toFixed(1) }} fps
        </span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import McapVideoStream from '@/components/records/McapVideoStream.vue'
import {
  exportTrackAsMp4, Mp4ExportProgress, Mp4ExportRange, saveBlob,
} from '@/libs/mcap/export'
import {
  isMediaSourceSupported, McapVideoRecording, McapVideoStats, openMcapVideoRecording,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'
import { prettifySize } from '@/utils/helper_functions'

/** How far a stream may drift from the one being controlled before it is nudged back into place. */
const SYNC_TOLERANCE_SECONDS = 0.5
/** `HTMLMediaElement.HAVE_CURRENT_DATA`: the element has a frame for its current position. */
const HAVE_CURRENT_DATA = 2
/** How finely the picker cuts. Bounds land on multiples of it, so the end of a recording lies within. */
const CLIP_STEP_SECONDS = 0.1
/** Room the range slider leaves on each side for its thumbs, which the playhead marker has to match. */
const SLIDER_THUMB_ROOM = '8px'
/** Time between progress updates, so that saving does not repaint the page on every frame. */
const PROGRESS_INTERVAL_MS = 200

function formatPosition(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor(total % 3600 / 60)
  const secs = total % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }
  return `${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export default Vue.extend({
  name: 'McapVideoPlayer',
  components: {
    McapVideoStream,
  },
  props: {
    url: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      recording: null as McapVideoRecording | null,
      tracks: [] as VideoTrack[],
      videos: [] as HTMLVideoElement[],
      stream_stats: {} as Record<number, McapVideoStats>,
      bytes_downloaded: 0,
      error: null as string | null,
      opening: true,
      statistics: false,
      clip_range: [0, 0],
      moved_bound: 0,
      position: 0,
      export_progress: null as Mp4ExportProgress | null,
      export_track_name: null as string | null,
      export_track_index: 0,
      export_track_count: 0,
      export_controller: null as AbortController | null,
      last_progress_at: 0,
    }
  },
  computed: {
    columns(): number {
      return Math.min(this.tracks.length, 2)
    },
    duration(): number {
      return this.recording?.durationSeconds ?? 0
    },
    clip_step(): number {
      return CLIP_STEP_SECONDS
    },
    /** Part of the recording the streams save, or null while they save all of it. */
    clip(): Mp4ExportRange | null {
      const [start, end] = this.clip_range
      const toTheEnd = end >= this.duration - CLIP_STEP_SECONDS
      const whole = start <= 0 && toTheEnd
      if (whole) {
        return null
      }
      return { startSeconds: start, endSeconds: toTheEnd ? Infinity : end }
    },
    clip_duration_label(): string {
      const [start, end] = this.clip_range
      return formatPosition(Math.max(0, Math.round(end) - Math.round(start)))
    },
    save_label(): string {
      if (!this.clip) {
        return this.tracks.length > 1
          ? `Saving ${this.tracks.length} whole streams`
          : 'Saving the whole stream'
      }
      return `Selected ${this.positionLabel(this.clip_range[0])} – ${this.positionLabel(this.clip_range[1])}`
    },
    export_button_label(): string {
      if (this.clip) {
        return 'Save selected range'
      }
      return this.tracks.length > 1 ? 'Save all as MP4' : 'Save as MP4'
    },
    export_percentage(): number {
      const { seconds, durationSeconds } = this.export_progress ?? { seconds: 0, durationSeconds: 0 }
      const current = durationSeconds > 0 ? Math.min(1, seconds / durationSeconds) : 0
      if (this.export_track_count <= 1) {
        return Math.round(current * 100)
      }
      const done = this.export_track_index + current
      return Math.min(100, Math.round(done / this.export_track_count * 100))
    },
    export_status(): string {
      const size = prettifySize((this.export_progress?.bytes ?? 0) / 1024)
      if (this.export_track_count > 1 && this.export_track_name) {
        return `Saving ${this.export_track_index + 1}/${this.export_track_count}`
          + ` · ${this.export_track_name} · ${size}`
      }
      return `Saving MP4 · ${size}`
    },
    /** Sits over the slider track, which is inset by the room its thumbs need. */
    playhead_style(): Record<string, string> {
      const fraction = this.duration > 0 ? Math.min(this.position / this.duration, 1) : 0
      return { left: `calc(${SLIDER_THUMB_ROOM} + (100% - 2 * ${SLIDER_THUMB_ROOM}) * ${fraction})` }
    },
    downloaded(): string {
      return prettifySize(this.bytes_downloaded / 1024)
    },
    /** Recording name, used to name the video files saved out of it. */
    name(): string {
      return decodeURIComponent(this.url.split('/').pop() ?? 'recording').replace(/\.mcap$/, '')
    },
    leader_stats(): McapVideoStats | null {
      const [track] = this.tracks
      return track ? this.stream_stats[track.channelId] ?? null : null
    },
  },
  async mounted() {
    if (!isMediaSourceSupported()) {
      this.error = 'This browser cannot play recordings, as it does not support Media Source Extensions.'
      this.opening = false
      return
    }

    try {
      this.recording = await openMcapVideoRecording(this.url)
      // Biggest stream first: it gets the playback controls the others follow.
      this.tracks = [...this.recording.tracks].sort((left, right) => right.frameCount - left.frameCount)
      this.clip_range = [0, this.recording.durationSeconds]
      if (this.tracks.length === 0) {
        this.error = 'This recording does not contain any video stream.'
      }
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error)
    }
    this.opening = false
  },
  beforeDestroy() {
    this.detachSync()
    this.export_controller?.abort()
  },
  methods: {
    onStreamReady(index: number, video: HTMLVideoElement): void {
      this.videos[index] = video
      if (index === 0) {
        video.addEventListener('play', this.syncFollowers)
        video.addEventListener('pause', this.syncFollowers)
        video.addEventListener('seeked', this.syncFollowers)
        video.addEventListener('timeupdate', this.syncFollowers)
        video.addEventListener('ratechange', this.syncFollowers)
        video.addEventListener('seeking', this.trackPosition)
        video.addEventListener('seeked', this.trackPosition)
        video.addEventListener('timeupdate', this.trackPosition)
      }
    },
    detachSync(): void {
      const [leader] = this.videos
      if (!leader) {
        return
      }
      leader.removeEventListener('play', this.syncFollowers)
      leader.removeEventListener('pause', this.syncFollowers)
      leader.removeEventListener('seeked', this.syncFollowers)
      leader.removeEventListener('timeupdate', this.syncFollowers)
      leader.removeEventListener('ratechange', this.syncFollowers)
      leader.removeEventListener('seeking', this.trackPosition)
      leader.removeEventListener('seeked', this.trackPosition)
      leader.removeEventListener('timeupdate', this.trackPosition)
    },
    /**
     * The streams share this position, as the others follow the one holding the controls. Media can
     * run a moment past the recorded span, which marks are kept within so they stay comparable to it.
     */
    playbackPosition(): number {
      const [leader] = this.videos
      return Math.min(leader?.currentTime ?? 0, this.duration)
    },
    trackPosition(): void {
      this.position = this.playbackPosition()
    },
    /**
     * Keeps the other streams on the time of the one being controlled. All streams share the
     * recording clock, since fragments are timestamped from the MCAP log time, so their positions can
     * be compared directly.
     */
    syncFollowers(): void {
      const [leader, ...followers] = this.videos
      // While the leader is still settling its own position, nudging the others only makes them
      // restart their reads for a time that is about to change again.
      if (!leader || leader.seeking || leader.readyState < HAVE_CURRENT_DATA) {
        return
      }
      for (const follower of followers) {
        if (follower.playbackRate !== leader.playbackRate) {
          follower.playbackRate = leader.playbackRate
        }
        const drifted = Math.abs(follower.currentTime - leader.currentTime) > SYNC_TOLERANCE_SECONDS
        if (drifted && !follower.seeking) {
          follower.currentTime = leader.currentTime
        }
        if (leader.paused && !follower.paused) {
          follower.pause()
        } else if (!leader.paused && follower.paused) {
          follower.play().catch(() => undefined)
        }
      }
    },
    positionLabel(seconds: number): string {
      return formatPosition(seconds)
    },
    onRangeInput(range: number[]): void {
      const [start, end] = this.clip_range
      this.moved_bound = Math.abs(range[0] - start) >= Math.abs(range[1] - end) ? 0 : 1
      this.clip_range = range
    },
    /** Shows the frame at the bound just dragged, once dragging stops: seeking on every step thrashes reads. */
    onRangeSettled(range: number[]): void {
      const [leader] = this.videos
      const target = range[this.moved_bound]
      // A bound dropped where the playhead already sits would restart every read for the same frame.
      if (leader && Math.abs(leader.currentTime - target) > CLIP_STEP_SECONDS) {
        leader.currentTime = target
      }
    },
    /**
     * Marks are taken from the stream holding the controls, whose time the others follow. A mark
     * placed past the opposite bound takes the rest of the recording with it, rather than leaving
     * nothing to save.
     */
    markClipStart(): void {
      const [, end] = this.clip_range
      const at = this.playbackPosition()
      this.clip_range = [at, end > at ? end : this.duration]
    },
    markClipEnd(): void {
      const [start] = this.clip_range
      const at = this.playbackPosition()
      this.clip_range = [start < at ? start : 0, at]
    },
    onStats(index: number, stats: McapVideoStats): void {
      const track = this.tracks[index]
      if (track) {
        this.$set(this.stream_stats, track.channelId, stats)
      }
      // Every stream reports the same figure, since they read the recording through one reader.
      this.bytes_downloaded = stats.bytesDownloaded
    },
    /** Recording, stream and, when only a part is saved, the seconds it covers. */
    fileName(track: VideoTrack, clip: Mp4ExportRange | null): string {
      const base = `${this.name}-${track.name}`
      if (!clip) {
        return `${base}.mp4`
      }
      const end = Number.isFinite(clip.endSeconds) ? `${Math.round(clip.endSeconds)}s` : 'end'
      return `${base}-${Math.round(clip.startSeconds)}s-${end}.mp4`
    },
    async saveMp4(): Promise<void> {
      if (!this.recording || this.tracks.length === 0 || this.export_progress) {
        return
      }
      const controller = new AbortController()
      // Held for the whole export, so moving the marks meanwhile cannot rename what is being saved.
      const { clip } = this
      const end = Math.min(clip?.endSeconds ?? Infinity, this.recording.durationSeconds)
      const durationSeconds = Math.max(end - (clip?.startSeconds ?? 0), 0)
      this.export_controller = controller
      this.export_track_count = this.tracks.length
      try {
        for (let index = 0; index < this.tracks.length; index += 1) {
          if (controller.signal.aborted) {
            return
          }
          const track = this.tracks[index]
          this.export_track_index = index
          this.export_track_name = track.name
          this.export_progress = { seconds: 0, durationSeconds, bytes: 0 }
          // eslint-disable-next-line no-await-in-loop
          const file = await exportTrackAsMp4(this.recording, track, {
            range: clip ?? undefined,
            signal: controller.signal,
            onProgress: (progress) => {
              const now = Date.now()
              if (now - this.last_progress_at >= PROGRESS_INTERVAL_MS) {
                this.last_progress_at = now
                this.export_progress = progress
              }
            },
          })
          saveBlob(file, this.fileName(track, clip))
        }
      } catch (error) {
        if (!(error instanceof Error) || error.name !== 'AbortError') {
          this.error = error instanceof Error ? error.message : String(error)
        }
      } finally {
        this.export_controller = null
        this.export_progress = null
        this.export_track_name = null
        this.export_track_index = 0
        this.export_track_count = 0
      }
    },
    cancelExport(): void {
      this.export_controller?.abort()
    },
  },
})
</script>

<style scoped>
.player {
  width: 100%;
}

.stream-grid {
  display: grid;
  gap: 12px;
}

.stream-grid.columns-2 {
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}

.export-panel {
  border: 1px solid rgba(128, 128, 128, 0.35);
  border-radius: 8px;
  background: rgba(128, 128, 128, 0.08);
}

.range-wrapper {
  position: relative;
  flex: 1;
}

.playhead {
  position: absolute;
  top: 50%;
  width: 2px;
  height: 14px;
  transform: translate(-1px, -50%);
  opacity: 0.7;
  pointer-events: none;
}

.bound-group {
  min-width: 64px;
}

.bound-value {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.export-progress {
  min-width: 0;
}

.stats-chip {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
</style>
