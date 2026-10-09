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

    <div v-if="opening" class="d-flex flex-column align-center py-8 px-4">
      <v-progress-circular
        :indeterminate="opening_percent === null"
        :value="opening_percent ?? 0"
        color="primary"
        size="64"
        width="5"
      >
        <span v-if="opening_percent !== null" class="caption">
          {{ Math.round(opening_percent) }}%
        </span>
      </v-progress-circular>
      <span class="mt-3 caption grey--text text-center">
        {{ opening_message }}
      </span>
      <span v-if="opening_status" class="mt-1 caption grey--text text-center">
        {{ opening_status }}
      </span>
    </div>

    <div
      v-if="recording && tracks.length > 0"
      class="player-stage"
    >
      <div
        v-if="visible_tracks.length === 0"
        class="stream-empty caption text-center py-8"
      >
        Select at least one stream to play.
      </div>
      <div
        v-else
        class="stream-grid"
        :style="grid_style"
      >
        <mcap-video-stream
          v-for="track in visible_tracks"
          :key="track.channelId"
          ref="stream"
          :recording="recording"
          :track="track"
          :ongoing="ongoing"
          :available="trackCovers(track, position)"
          :position="position"
          :statistics="statistics"
          @ready="onStreamReady(track.channelId, $event)"
          @stats="onStats(track.channelId, $event)"
          @timeupdate="onStreamTime(track.channelId, $event)"
          @play="onLeaderPlay"
          @pause="onLeaderPause"
          @progress="updateBuffered"
          @extended="onExtended"
        />
      </div>

      <div class="playback-bar">
        <div class="d-flex align-center">
          <v-btn
            v-tooltip="playing ? 'Pause' : 'Play'"
            icon
            small
            dark
            @click="togglePlayback"
          >
            <v-icon>
              {{ playing ? 'mdi-pause' : 'mdi-play' }}
            </v-icon>
          </v-btn>
          <v-btn
            v-if="ongoing"
            v-tooltip="at_latest
              ? 'Showing the latest recorded frames'
              : 'Skip to the latest recorded frames'"
            icon
            small
            dark
            class="ml-1"
            :color="at_latest ? 'primary' : 'white'"
            @click="skipToLatest"
          >
            <v-icon>
              mdi-fast-forward
            </v-icon>
          </v-btn>
          <span class="caption mx-2 playback-time">
            {{ positionLabel(position) }} / {{ positionLabel(duration) }}
          </span>
          <v-spacer />
          <span
            v-if="ongoing && !at_latest"
            class="caption mr-2"
          >
            {{ frame_age_label }}
          </span>
          <v-menu
            v-if="tracks.length > 0"
            v-model="stream_menu"
            offset-y
            left
            :close-on-content-click="false"
            max-height="420"
          >
            <template #activator="{ on, attrs }">
              <v-btn
                v-tooltip="'Choose which streams to show'"
                small
                dark
                text
                class="stream-picker-btn"
                v-bind="attrs"
                v-on="on"
              >
                <v-icon small left>
                  mdi-video-outline
                </v-icon>
                Streams {{ visible_tracks.length }}/{{ tracks.length }}
              </v-btn>
            </template>
            <v-card class="stream-picker" dark>
              <v-card-text class="pb-1">
                <v-text-field
                  v-model="stream_search"
                  dense
                  hide-details
                  outlined
                  clearable
                  dark
                  label="Search streams"
                  prepend-inner-icon="mdi-magnify"
                />
              </v-card-text>
              <v-list
                dense
                dark
                class="py-0 stream-picker-list"
              >
                <v-list-item
                  v-for="track in filtered_tracks"
                  :key="track.channelId"
                  @click="toggleStream(track.channelId)"
                >
                  <v-list-item-action class="mr-2">
                    <v-checkbox
                      :input-value="selected_channel_ids.includes(track.channelId)"
                      dense
                      hide-details
                      color="primary"
                      @click.stop="toggleStream(track.channelId)"
                    />
                  </v-list-item-action>
                  <v-list-item-content>
                    <v-list-item-title>{{ track.name }}</v-list-item-title>
                    <v-list-item-subtitle>
                      {{ track.frameCount.toLocaleString() }} frames
                    </v-list-item-subtitle>
                  </v-list-item-content>
                </v-list-item>
                <v-list-item v-if="filtered_tracks.length === 0">
                  <v-list-item-title class="grey--text">
                    No matching streams
                  </v-list-item-title>
                </v-list-item>
              </v-list>
              <v-card-actions>
                <v-btn small text @click="selectAllStreams">
                  Select all
                </v-btn>
                <v-btn small text @click="selectNoStreams">
                  None
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-menu>
        </div>
        <div
          ref="timeline"
          class="timeline mt-1"
          :class="{ 'timeline-over-video': pointer_over_video }"
          role="slider"
          :aria-valuemin="0"
          :aria-valuemax="duration"
          :aria-valuenow="position"
          @pointerdown="onTimelineDown"
          @pointermove="onTimelineMove"
          @pointerup="onTimelineUp"
          @pointercancel="onTimelineUp"
          @pointerleave="onTimelineLeave"
        >
          <div class="timeline-track" />
          <div
            v-for="(range, index) in video_styles"
            :key="`video-${index}`"
            class="timeline-video"
            :style="range.style"
          >
            <span class="timeline-mark timeline-mark-start">&gt;</span>
            <span class="timeline-mark timeline-mark-end">&lt;</span>
          </div>
          <div
            v-for="(range, index) in buffered_styles"
            :key="`buffered-${index}`"
            class="timeline-buffered"
            :style="range"
          />
          <div
            class="timeline-playhead"
            :style="{ left: playhead_percent }"
          />
          <div
            v-if="pointer_seconds !== null"
            class="timeline-hover"
            :style="{ left: hover_percent }"
          >
            {{ positionLabel(pointer_seconds) }}
          </div>
        </div>
      </div>
    </div>

    <v-alert
      v-if="recording && tracks.length === 0"
      type="info"
      dense
      class="mb-2"
    >
      This recording has no video streams. CSV export is still available.
    </v-alert>

    <div
      v-if="recording && (tracks.length > 0 || recording.channels.length > 0)"
      class="player-footer mt-3"
    >
      <div class="d-flex align-center caption grey--text text--darken-1 mb-2 flex-wrap">
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
        <div
          v-if="tracks.length > 0"
          v-tooltip="statistics ? 'Hide detailed statistics' : 'Show detailed statistics'"
          class="d-flex align-center stats-toggle"
        >
          <span class="mr-2">Stats</span>
          <v-switch
            v-model="statistics"
            dense
            hide-details
            color="primary"
            class="mt-0 pt-0"
          />
        </div>
      </div>

      <v-checkbox
        v-model="cut_enabled"
        v-tooltip="'Export only part of the recording. Leave this off to keep the whole file.'"
        dense
        hide-details
        class="mt-0 pt-0 mb-2 cut-toggle"
        :disabled="Boolean(export_progress)"
        label="Cut the data before exporting"
        @change="onCutToggle"
      />

      <div v-if="cut_enabled" class="export-panel pa-3">
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
          <div class="bound-group mr-4 mb-1">
            <div class="caption grey--text text--darken-1">
              Start
            </div>
            <div class="bound-value primary--text">
              {{ positionLabel(clip_range[0]) }}
            </div>
          </div>
          <div class="bound-group mr-4 mb-1">
            <div class="caption grey--text text--darken-1">
              End
            </div>
            <div class="bound-value primary--text">
              {{ positionLabel(clip_range[1]) }}
            </div>
          </div>
          <div class="bound-group mr-4 mb-1">
            <div class="caption grey--text text--darken-1">
              Duration
            </div>
            <div class="bound-value primary--text">
              {{ clip_duration_label }}
            </div>
          </div>
          <v-spacer />
          <v-btn
            v-tooltip="'Use the whole recording again'"
            small
            text
            class="mr-1"
            @click="resetClip"
          >
            Whole recording
          </v-btn>
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
      </div>

      <div class="d-flex align-center flex-wrap mt-3 action-row">
        <template v-if="export_progress">
          <div class="export-progress flex-grow-1 mr-3 mb-2">
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
            <div class="caption warning--text mt-1">
              Keep this page open. Leaving now will stop this export.
            </div>
          </div>
          <v-btn
            small
            text
            class="mr-2 mb-2"
            @click="cancelExport"
          >
            Cancel
          </v-btn>
        </template>
        <v-spacer />
        <div class="action-group d-flex flex-wrap justify-end">
          <v-btn
            v-if="recording && recording.channels.length > 0"
            v-tooltip="'Choose topics and save them as CSV. Listing every topic downloads more of the recording.'"
            small
            outlined
            color="primary"
            class="mr-2 mb-2"
            :disabled="Boolean(export_progress)"
            @click="openCsvExport"
          >
            <v-icon small left>
              mdi-table-arrow-down
            </v-icon>
            Export data
          </v-btn>
          <v-btn
            v-tooltip="save_label"
            small
            outlined
            color="primary"
            class="mb-2"
            :loading="Boolean(export_progress)"
            :disabled="Boolean(export_progress) || tracks.length === 0"
            @click="saveMp4"
          >
            <v-icon small left>
              mdi-video-outline
            </v-icon>
            Export video
          </v-btn>
        </div>
      </div>

      <div
        v-if="statistics && leader_stats"
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

    <v-alert
      v-if="page_busy"
      type="warning"
      dense
      class="mt-3 mb-0"
    >
      Keep this page open. This export runs in the browser and will stop if you leave or close this window.
    </v-alert>

    <v-dialog
      v-model="csv_open"
      :fullscreen="$vuetify.breakpoint.xsOnly"
      max-width="800"
      scrollable
      :persistent="csv_busy"
    >
      <v-card>
        <v-card-title class="d-flex align-center">
          Export data
          <v-spacer />
          <v-btn
            v-tooltip="csv_busy ? 'Wait until the export finishes' : 'Close'"
            icon
            small
            color="primary"
            :disabled="csv_busy"
            @click="csv_open = false"
          >
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <div v-if="naming_channels" class="d-flex flex-column align-center py-8 px-4">
            <v-progress-circular
              :indeterminate="naming_percent === null"
              :value="naming_percent ?? 0"
              color="primary"
              size="64"
              width="5"
            >
              <span v-if="naming_percent !== null" class="caption">
                {{ Math.round(naming_percent) }}%
              </span>
            </v-progress-circular>
            <span class="mt-3 caption grey--text text-center">
              Listing every topic in this recording...
            </span>
            <span v-if="naming_status" class="mt-1 caption grey--text text-center">
              {{ naming_status }}
            </span>
          </div>
          <mcap-csv-export
            v-else-if="recording"
            :recording="recording"
            :clip="clip"
            :name="name"
            @error="onCsvError"
            @busy="onCsvBusy"
          />
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import { saveAs } from 'file-saver'
import Vue from 'vue'

import McapCsvExport from '@/components/records/McapCsvExport.vue'
import McapVideoStream from '@/components/records/McapVideoStream.vue'
import { listMcapChannels } from '@/libs/mcap/channels'
import {
  exportTrackAsMp4, Mp4ExportProgress, Mp4ExportRange,
} from '@/libs/mcap/export'
import {
  isMediaSourceSupported, McapVideoRecording, McapVideoStats, McapVideoSummary, openMcapVideoRecording,
} from '@/libs/mcap/player'
import { PrefixScanProgress } from '@/libs/mcap/reader'
import {
  listVideoTracks, mergeTimeRanges, TimeRange, timeRangesCover, VideoTrack,
} from '@/libs/mcap/video-track'
import { prettifySize } from '@/utils/helper_functions'

/** How far a stream may drift from the one being controlled before it is nudged back into place. */
const SYNC_TOLERANCE_SECONDS = 0.5
/** `HTMLMediaElement.HAVE_CURRENT_DATA`: the element has a frame for its current position. */
const HAVE_CURRENT_DATA = 2
/** How close to the last recorded frame counts as watching the latest written frames. */
const LATEST_EDGE_SECONDS = 2
/** How finely the picker cuts. Bounds land on multiples of it, so the end of a recording lies within. */
const CLIP_STEP_SECONDS = 0.1
/** Room the range slider leaves on each side for its thumbs, which the playhead marker has to match. */
const SLIDER_THUMB_ROOM = '8px'
/** Cap on grid columns so 64 streams stay readable on a desktop layout. */
const MAX_GRID_COLUMNS = 8

function coverageEnd(tracks: VideoTrack[]): number {
  let latest = 0
  for (const track of tracks) {
    for (const range of track.coverage) {
      latest = Math.max(latest, range.end)
    }
  }
  return latest
}

function coverageStart(tracks: VideoTrack[]): number {
  let earliest = Number.POSITIVE_INFINITY
  for (const track of tracks) {
    for (const range of track.coverage) {
      earliest = Math.min(earliest, range.start)
    }
  }
  return Number.isFinite(earliest) ? earliest : 0
}

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

function formatFrameAge(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds))
  if (whole === 0) {
    return 'Frame from less than a second ago'
  }
  return whole === 1 ? 'Frame from 1 second ago' : `Frame from ${whole} seconds ago`
}

export default Vue.extend({
  name: 'McapVideoPlayer',
  components: {
    McapCsvExport,
    McapVideoStream,
  },
  props: {
    url: {
      type: String,
      required: true,
    },
    indexUrl: {
      type: String,
      default: undefined,
    },
    ongoing: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      recording: null as McapVideoRecording | null,
      tracks: [] as VideoTrack[],
      selected_channel_ids: [] as number[],
      videos: {} as Record<number, HTMLVideoElement>,
      stream_stats: {} as Record<number, McapVideoStats>,
      bytes_downloaded: 0,
      error: null as string | null,
      opening: true,
      open_progress: null as PrefixScanProgress | null,
      opening_bytes_per_second: 0,
      statistics: false,
      csv_open: false,
      csv_busy: false,
      naming_channels: false,
      naming_progress: null as { named: number, total: number, bytes: number, bytesPerSecond: number } | null,
      naming_controller: null as AbortController | null,
      cut_enabled: false,
      clip_range: [0, 0],
      moved_bound: 0,
      position: 0,
      export_progress: null as Mp4ExportProgress | null,
      export_track_name: null as string | null,
      export_track_index: 0,
      export_track_count: 0,
      open_controller: new AbortController(),
      export_controller: null as AbortController | null,
      playing: false,
      pending_seek: null as number | null,
      timeline_dragging: false,
      pointer_over_video: false,
      stream_menu: false,
      stream_search: '',
      follow_timer: null as ReturnType<typeof setInterval> | null,
      buffered_ranges: [] as { start: number, end: number }[],
      pointer_seconds: null as number | null,
    }
  },
  computed: {
    visible_tracks(): VideoTrack[] {
      const selected = new Set(this.selected_channel_ids)
      return this.tracks.filter((track) => selected.has(track.channelId))
    },
    filtered_tracks(): VideoTrack[] {
      const query = this.stream_search.trim().toLowerCase()
      if (!query) {
        return this.tracks
      }
      return this.tracks.filter((track) => track.name.toLowerCase().includes(query)
        || track.topic.toLowerCase().includes(query))
    },
    columns(): number {
      const count = this.visible_tracks.length
      if (count <= 1 || this.$vuetify.breakpoint.smAndDown) {
        return 1
      }
      return Math.min(MAX_GRID_COLUMNS, Math.ceil(Math.sqrt(count)))
    },
    grid_rows(): number {
      const count = this.visible_tracks.length
      return Math.max(1, Math.ceil(count / this.columns))
    },
    grid_style(): Record<string, string> {
      return {
        '--grid-columns': String(this.columns),
        '--grid-rows': String(this.grid_rows),
      }
    },
    duration(): number {
      return this.recording?.durationSeconds ?? 0
    },
    clip_step(): number {
      return CLIP_STEP_SECONDS
    },
    /** Part of the recording the streams save, or null while they save all of it. */
    clip(): Mp4ExportRange | null {
      if (!this.cut_enabled) {
        return null
      }
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
          ? `Save ${this.tracks.length} whole streams as MP4`
          : 'Save the whole stream as MP4'
      }
      return `Save ${this.positionLabel(this.clip_range[0])} – ${this.positionLabel(this.clip_range[1])} as MP4`
    },
    page_busy(): boolean {
      return Boolean(this.export_progress) || this.csv_busy
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
    opening_message(): string {
      return this.ongoing
        ? 'This is an on-going recording. Reading what has been written so far...'
        : 'Reading recording index...'
    },
    opening_status(): string {
      const progress = this.open_progress
      if (!progress) {
        return ''
      }
      const indexed = prettifySize(progress.offset / 1024)
      const total = prettifySize(progress.size / 1024)
      const chunks = progress.chunks === 1 ? '1 chunk' : `${progress.chunks} chunks`
      const speed = this.opening_bytes_per_second > 0
        ? ` · ${prettifySize(this.opening_bytes_per_second / 1024)}/s`
        : ''
      return `${indexed} of ${total} · ${chunks}${speed}`
    },
    opening_percent(): number | null {
      const progress = this.open_progress
      if (!progress || progress.size <= 0) {
        return null
      }
      return Math.min(100, progress.offset / progress.size * 100)
    },
    naming_status(): string {
      const progress = this.naming_progress
      if (!progress) {
        return ''
      }
      const speed = progress.bytesPerSecond > 0 ? ` · ${prettifySize(progress.bytesPerSecond / 1024)}/s` : ''
      return `${progress.named} of ${progress.total} topics · ${prettifySize(progress.bytes / 1024)}${speed}`
    },
    naming_percent(): number | null {
      const progress = this.naming_progress
      if (!progress || progress.total <= 0) {
        return null
      }
      return Math.min(100, progress.named / progress.total * 100)
    },
    /** Recording name, used to name the video files saved out of it. */
    name(): string {
      return decodeURIComponent(this.url.split('/').pop() ?? 'recording').replace(/\.mcap$/, '')
    },
    leader_stats(): McapVideoStats | null {
      const [track] = this.visible_tracks
      return track ? this.stream_stats[track.channelId] ?? null : null
    },
    video_coverage(): TimeRange[] {
      return mergeTimeRanges(this.visible_tracks.flatMap((track) => track.coverage))
    },
    last_video_time(): number {
      return coverageEnd(this.visible_tracks.length > 0 ? this.visible_tracks : this.tracks)
    },
    at_latest(): boolean {
      return this.ongoing && this.last_video_time - this.position <= LATEST_EDGE_SECONDS
    },
    frame_age_label(): string {
      return formatFrameAge(this.last_video_time - this.position)
    },
    playhead_percent(): string {
      if (this.duration <= 0) {
        return '0%'
      }
      return `${Math.min(100, this.position / this.duration * 100)}%`
    },
    hover_percent(): string {
      if (this.pointer_seconds === null || this.duration <= 0) {
        return '0%'
      }
      return `${Math.min(100, this.pointer_seconds / this.duration * 100)}%`
    },
    video_styles(): { style: { left: string, width: string } }[] {
      if (this.duration <= 0) {
        return []
      }
      return this.video_coverage.map((range) => ({
        style: {
          left: `${range.start / this.duration * 100}%`,
          width: `${Math.max(0, range.end - range.start) / this.duration * 100}%`,
        },
      }))
    },
    buffered_styles(): { left: string, width: string }[] {
      if (this.duration <= 0) {
        return []
      }
      return this.buffered_ranges.map((range) => ({
        left: `${range.start / this.duration * 100}%`,
        width: `${Math.max(0, range.end - range.start) / this.duration * 100}%`,
      }))
    },
  },
  watch: {
    page_busy: {
      immediate: true,
      handler(busy: boolean) {
        this.$emit('busy', busy)
      },
    },
    csv_open(open: boolean) {
      if (!open) {
        this.naming_controller?.abort()
      }
    },
  },
  async mounted() {
    try {
      const startedAt = Date.now()
      this.recording = await openMcapVideoRecording(this.url, {
        indexUrl: this.indexUrl,
        signal: this.open_controller.signal,
        onProgress: (progress) => {
          this.open_progress = progress
          const elapsed = (Date.now() - startedAt) / 1000
          this.opening_bytes_per_second = elapsed >= 0.25 ? progress.bytesRead / elapsed : 0
        },
      })
      this.tracks = this.recording.tracks
      this.selected_channel_ids = this.tracks.map((track) => track.channelId)
      this.clip_range = [0, this.recording.durationSeconds]
      if (this.ongoing) {
        this.position = coverageEnd(this.tracks) || this.recording.durationSeconds
        this.follow_timer = setInterval(() => {
          this.followRecording()
        }, 750)
      } else {
        this.position = coverageStart(this.tracks)
      }
      this.emitSummary()
      this.recording.reader.loadRemainingChunkIndexes(this.open_controller.signal, () => {
        this.onExtended()
      }).catch((error) => {
        if (!this.open_controller.signal.aborted) {
          console.warn('Failed to finish loading the recording index:', error)
        }
      })
      if (this.tracks.length > 0 && !isMediaSourceSupported()) {
        this.error = 'This browser cannot play recordings, as it does not support Media Source Extensions.'
      }
    } catch (error) {
      if (!this.open_controller.signal.aborted) {
        this.error = error instanceof Error ? error.message : String(error)
      }
    }
    this.opening = false
  },
  beforeDestroy() {
    if (this.follow_timer) {
      clearInterval(this.follow_timer)
      this.follow_timer = null
    }
    this.open_controller.abort()
    this.export_controller?.abort()
    this.naming_controller?.abort()
    this.$emit('busy', false)
  },
  methods: {
    trackCovers(track: VideoTrack, seconds: number): boolean {
      return timeRangesCover(track.coverage, seconds)
    },
    clockChannelId(): number | null {
      const available = this.visible_tracks.find((track) => this.trackCovers(track, this.position))
      return available?.channelId ?? this.visible_tracks[0]?.channelId ?? null
    },
    clockVideo(): HTMLVideoElement | null {
      const channelId = this.clockChannelId()
      return channelId === null ? null : this.videos[channelId] ?? null
    },
    onStreamReady(channelId: number, video: HTMLVideoElement): void {
      this.$set(this.videos, channelId, video)
    },
    /**
     * The streams share this position, as the others follow the one holding the controls. Media can
     * run a moment past the recorded span, which marks are kept within so they stay comparable to it.
     */
    playbackPosition(): number {
      const leader = this.clockVideo()
      return Math.min(leader?.currentTime ?? this.position, this.duration)
    },
    playheadHasMedia(video: HTMLVideoElement): boolean {
      const { buffered, currentTime } = video
      for (let index = 0; index < buffered.length; index += 1) {
        if (currentTime >= buffered.start(index) && currentTime <= buffered.end(index)) {
          return true
        }
      }
      return false
    },
    onStreamTime(channelId: number, seconds: number): void {
      if (this.timeline_dragging) {
        return
      }
      if (channelId !== this.clockChannelId()) {
        return
      }
      if (this.pending_seek !== null) {
        const leader = this.clockVideo()
        const target = this.pending_seek
        if (leader && !leader.seeking && this.playheadHasMedia(leader)) {
          this.pending_seek = null
          this.position = this.playbackPosition()
          return
        }
        this.position = target
        return
      }
      this.position = Math.min(seconds, this.duration)
    },
    updateBuffered(): void {
      const leader = this.clockVideo()
      if (!leader) {
        this.buffered_ranges = []
        return
      }
      const ranges = []
      for (let index = 0; index < leader.buffered.length; index += 1) {
        ranges.push({ start: leader.buffered.start(index), end: leader.buffered.end(index) })
      }
      this.buffered_ranges = ranges
    },
    onLeaderPlay(): void {
      this.playing = true
      this.syncFollowers()
    },
    onLeaderPause(): void {
      const leader = this.clockVideo()
      if (leader && !leader.paused) {
        return
      }
      this.playing = false
      this.syncFollowers()
    },
    togglePlayback(): void {
      if (this.playing) {
        this.streamRefs().forEach((stream) => stream.pause())
        this.playing = false
        return
      }
      if (!timeRangesCover(this.video_coverage, this.position) && this.video_coverage.length > 0) {
        this.seekTo(this.ongoing ? this.last_video_time : this.video_coverage[0].start)
        return
      }
      this.streamRefs().forEach((stream) => stream.play())
      this.playing = true
    },
    streamRefs(): { seek: (seconds: number) => void, play: () => void, pause: () => void }[] {
      const streams = this.$refs.stream as
        | { seek: (seconds: number) => void, play: () => void, pause: () => void }[]
        | { seek: (seconds: number) => void, play: () => void, pause: () => void }
      if (!streams) {
        return []
      }
      return Array.isArray(streams) ? streams : [streams]
    },
    seekTo(seconds: number): void {
      if (!timeRangesCover(this.video_coverage, seconds)) {
        return
      }
      const target = Math.max(0, Math.min(seconds, this.duration))
      this.pending_seek = target
      this.position = target
      for (const stream of this.streamRefs()) {
        stream.seek(target)
      }
      this.streamRefs().forEach((stream) => stream.play())
      this.playing = true
    },
    skipToLatest(): void {
      this.seekTo(this.last_video_time)
    },
    secondsFromPointer(event: PointerEvent): number {
      const timeline = this.$refs.timeline as HTMLElement
      const rect = timeline.getBoundingClientRect()
      if (rect.width <= 0) {
        return 0
      }
      const fraction = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width))
      return fraction * this.duration
    },
    onTimelineDown(event: PointerEvent): void {
      const seconds = this.secondsFromPointer(event)
      this.pointer_seconds = seconds
      this.pointer_over_video = timeRangesCover(this.video_coverage, seconds)
      if (!this.pointer_over_video) {
        return
      }
      event.preventDefault()
      this.timeline_dragging = true
      const timeline = event.currentTarget as HTMLElement
      timeline.setPointerCapture(event.pointerId)
      this.pending_seek = seconds
      this.position = seconds
    },
    onTimelineMove(event: PointerEvent): void {
      const seconds = this.secondsFromPointer(event)
      this.pointer_seconds = seconds
      this.pointer_over_video = timeRangesCover(this.video_coverage, seconds)
      if (!this.timeline_dragging) {
        return
      }
      if (!this.pointer_over_video) {
        return
      }
      this.pending_seek = seconds
      this.position = seconds
    },
    onTimelineUp(event: PointerEvent): void {
      if (!this.timeline_dragging) {
        return
      }
      this.timeline_dragging = false
      this.seekTo(this.secondsFromPointer(event))
    },
    onTimelineLeave(): void {
      if (this.timeline_dragging) {
        return
      }
      this.pointer_seconds = null
      this.pointer_over_video = false
    },
    toggleStream(channelId: number): void {
      if (this.selected_channel_ids.includes(channelId)) {
        this.selected_channel_ids = this.selected_channel_ids.filter(
          (selected) => selected !== channelId,
        )
        return
      }
      this.selected_channel_ids = this.tracks
        .map((track) => track.channelId)
        .filter((selected) => selected === channelId || this.selected_channel_ids.includes(selected))
    },
    selectAllStreams(): void {
      this.selected_channel_ids = this.tracks.map((track) => track.channelId)
    },
    selectNoStreams(): void {
      this.selected_channel_ids = []
    },
    async followRecording(): Promise<void> {
      if (!this.recording) {
        return
      }
      try {
        if (await this.recording.reader.extendWrittenPrefix(this.open_controller.signal)) {
          this.onExtended()
        }
      } catch {
        // A failed poll is retried on the next interval; playback keeps what it already has.
      }
    },
    onExtended(): void {
      if (!this.recording) {
        return
      }
      const { reader } = this.recording
      this.recording.durationSeconds = Number(reader.summary.endTime - this.recording.startTime) / 1e9
      const listed = listVideoTracks(reader)
      const selected = new Set(this.selected_channel_ids)
      const known = new Set(this.tracks.map((track) => track.channelId))
      for (const track of listed) {
        if (!known.has(track.channelId)) {
          selected.add(track.channelId)
        }
      }
      this.tracks = listed
      this.selected_channel_ids = listed
        .map((track) => track.channelId)
        .filter((channelId) => selected.has(channelId))
      this.emitSummary()
    },
    emitSummary(): void {
      const { recording } = this
      if (!recording) {
        return
      }
      const summary: McapVideoSummary = {
        durationSeconds: recording.durationSeconds,
        started: Number(recording.startTime) / 1e9,
        ended: Number(recording.startTime) / 1e9 + recording.durationSeconds,
        tracks: this.tracks,
        channels: recording.channels,
        bytesRead: recording.reader.source.bytesRead,
      }
      this.$emit('summary', summary)
    },
    /**
     * Keeps the other streams on the time of the one being controlled. All streams share the
     * recording clock, since fragments are timestamped from the MCAP log time, so their positions can
     * be compared directly.
     */
    syncFollowers(): void {
      const leader = this.clockVideo()
      // While the leader is still settling its own position, nudging the others only makes them
      // restart their reads for a time that is about to change again.
      if (!leader || leader.seeking || leader.readyState < HAVE_CURRENT_DATA) {
        return
      }
      for (const track of this.visible_tracks) {
        const follower = this.videos[track.channelId]
        if (!follower || follower === leader || !this.trackCovers(track, leader.currentTime)) {
          continue
        }
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
      const target = range[this.moved_bound]
      if (Math.abs(this.position - target) > CLIP_STEP_SECONDS) {
        this.seekTo(target)
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
    resetClip(): void {
      this.clip_range = [0, this.duration]
    },
    onCutToggle(enabled: boolean): void {
      if (enabled && this.clip_range[1] <= this.clip_range[0]) {
        this.resetClip()
      }
    },
    onCsvBusy(busy: boolean): void {
      this.csv_busy = busy
    },
    /**
     * Opening an ongoing recording only names the channels its budget reached, so the topic list is
     * completed here, where the user has asked for topics and can be shown that it takes a moment.
     */
    async openCsvExport(): Promise<void> {
      this.csv_open = true
      const { recording } = this
      if (!recording || recording.reader.unnamedChannelCount === 0) {
        return
      }
      const total = recording.channels.length + recording.reader.unnamedChannelCount
      const controller = new AbortController()
      this.naming_controller = controller
      this.naming_progress = {
        named: recording.channels.length, total, bytes: 0, bytesPerSecond: 0,
      }
      this.naming_channels = true
      const startedAt = Date.now()
      let startedBytes: number | null = null
      try {
        const named = await recording.reader.nameRemainingChannels(controller.signal, (progress) => {
          startedBytes ??= progress.bytesRead
          const elapsed = (Date.now() - startedAt) / 1000
          const bytes = progress.bytesRead - startedBytes
          this.naming_progress = {
            named: total - recording.reader.unnamedChannelCount,
            total,
            bytes,
            bytesPerSecond: elapsed >= 0.25 ? bytes / elapsed : 0,
          }
        })
        if (named) {
          recording.channels = listMcapChannels(recording.reader)
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          this.error = error instanceof Error ? error.message : String(error)
        }
      }
      if (this.naming_controller === controller) {
        this.naming_channels = false
        this.naming_progress = null
        this.naming_controller = null
      }
    },
    onStats(channelId: number, stats: McapVideoStats): void {
      this.$set(this.stream_stats, channelId, stats)
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
              this.export_progress = progress
            },
          })
          saveAs(file, this.fileName(track, clip))
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
    onCsvError(message: string): void {
      this.error = message
    },
  },
})
</script>

<style scoped>
.player {
  width: 100%;
}

.player-stage {
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}

.stream-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(var(--grid-columns, 1), minmax(0, 1fr));
  padding: 8px 8px 0;
}

.stream-empty {
  color: #e5e7eb;
}

.playback-bar {
  background: #000;
  color: #e5e7eb;
  padding: 4px 12px 12px;
}

.playback-time {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.stream-picker-btn {
  text-transform: none;
}

.stream-picker {
  min-width: 280px;
  background: #000;
}

.stream-picker-list {
  max-height: 280px;
  overflow-y: auto;
}

.timeline {
  position: relative;
  height: 18px;
  cursor: default;
  touch-action: none;
}

.timeline-over-video {
  cursor: pointer;
}

.timeline-track {
  position: absolute;
  left: 0;
  right: 0;
  top: 8px;
  height: 4px;
  border-radius: 2px;
  background: #2a2a2a;
}

.timeline-video {
  position: absolute;
  top: 8px;
  height: 4px;
  border-radius: 2px;
  background: #6b7280;
  pointer-events: none;
}

.timeline-mark {
  position: absolute;
  top: -9px;
  font-size: 10px;
  line-height: 1;
  color: #fff;
  pointer-events: none;
}

.timeline-mark-start {
  left: 0;
  transform: translateX(-50%);
}

.timeline-mark-end {
  right: 0;
  transform: translateX(50%);
}

.timeline-buffered {
  position: absolute;
  top: 8px;
  height: 4px;
  border-radius: 2px;
  background: #d1d5db;
  pointer-events: none;
}

.timeline-playhead {
  position: absolute;
  top: 5px;
  width: 10px;
  height: 10px;
  margin-left: -5px;
  border-radius: 50%;
  background: #fff;
  pointer-events: none;
}

.timeline-hover {
  position: absolute;
  bottom: 100%;
  z-index: 2;
  padding: 2px 6px;
  margin-bottom: 4px;
  border-radius: 3px;
  background: rgba(0, 0, 0, 0.85);
  color: #fff;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  white-space: nowrap;
  pointer-events: none;
  transform: translateX(-50%);
}

.action-group {
  min-width: 0;
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

.cut-toggle {
  max-width: 100%;
}

.stats-toggle ::v-deep .v-input--selection-controls {
  margin-top: 0;
  padding-top: 0;
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
