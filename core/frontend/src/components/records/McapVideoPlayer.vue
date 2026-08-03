<template>
  <div>
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
        :name="name"
        :controls="index === 0"
        :statistics="statistics"
        :clip="clip"
        @ready="onStreamReady(index, $event)"
        @stats="onStats"
        @export-error="onExportError"
      />
    </div>

    <div v-if="tracks.length > 0" class="mt-2">
      <div class="d-flex align-center caption grey--text text--darken-1">
        <span
          v-if="bytes_downloaded > 0"
          v-tooltip="'Only the parts of the recording you watch are downloaded from the vehicle'"
          class="mr-3"
        >
          {{ downloaded }} downloaded
        </span>
        <span v-if="tracks.length > 1">
          {{ tracks.length }} streams playing together, sharing the same download
        </span>
        <v-spacer />
        <v-btn
          v-tooltip="picking_clip ? 'Save whole streams again' : 'Choose which part of the streams to save'"
          icon
          x-small
          :color="picking_clip ? 'primary' : undefined"
          @click="toggleClipPicker"
        >
          <v-icon small>
            mdi-content-cut
          </v-icon>
        </v-btn>
        <v-btn
          v-tooltip="statistics ? 'Hide stream statistics' : 'Show stream statistics'"
          icon
          x-small
          :color="statistics ? 'primary' : undefined"
          @click="statistics = !statistics"
        >
          <v-icon small>
            mdi-chart-box-outline
          </v-icon>
        </v-btn>
      </div>

      <div v-if="picking_clip" class="mt-1">
        <div class="d-flex align-center caption grey--text text--darken-1">
          <span>0:00</span>
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
        <div class="d-flex align-center caption grey--text text--darken-1">
          <span v-tooltip="'Saving starts from the keyframe before the chosen point'">
            {{ clip_label }}
          </span>
          <v-spacer />
          <v-btn
            v-tooltip="'Move the start of the saved part to the playback position'"
            x-small
            text
            @click="markClipStart"
          >
            <v-icon x-small left>
              mdi-ray-start
            </v-icon>
            start here
          </v-btn>
          <v-btn
            v-tooltip="'Move the end of the saved part to the playback position'"
            x-small
            text
            @click="markClipEnd"
          >
            <v-icon x-small left>
              mdi-ray-end
            </v-icon>
            end here
          </v-btn>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import McapVideoStream from '@/components/records/McapVideoStream.vue'
import { Mp4ExportRange } from '@/libs/mcap/export'
import {
  isMediaSourceSupported, McapVideoRecording, McapVideoStats, openMcapVideoRecording,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'
import { prettifySize } from '@/utils/helper_functions'

/** How far a stream may drift from the one being controlled before it is nudged back into place. */
const SYNC_TOLERANCE_SECONDS = 0.5
/** `HTMLMediaElement.HAVE_CURRENT_DATA`: the element has a frame for its current position. */
const HAVE_CURRENT_DATA = 2
/** Part offered when the picker opens, so that there is something to drag rather than a full range. */
const DEFAULT_CLIP_SECONDS = 30
/** How finely the picker cuts. Bounds land on multiples of it, so the end of a recording lies within. */
const CLIP_STEP_SECONDS = 0.1
/** Room the range slider leaves on each side for its thumbs, which the playhead marker has to match. */
const SLIDER_THUMB_ROOM = '8px'

function formatPosition(seconds: number): string {
  const total = Math.round(seconds)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** Reads a length as minutes and seconds, or as seconds alone while it is short. */
function formatLength(seconds: number): string {
  const total = Math.round(seconds)
  return total < 60 ? `${total} s` : formatPosition(total)
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
      bytes_downloaded: 0,
      error: null as string | null,
      opening: true,
      statistics: false,
      picking_clip: false,
      clip_range: [0, 0],
      moved_bound: 0,
      position: 0,
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
      if (!this.picking_clip || whole) {
        return null
      }
      return { startSeconds: start, endSeconds: toTheEnd ? Infinity : end }
    },
    clip_label(): string {
      if (!this.clip) {
        return 'saving the whole recording'
      }
      const [start, end] = this.clip_range
      // Length from the shown bounds, so that it always adds up for whoever reads the three of them.
      const length = Math.round(end) - Math.round(start)
      return `saving ${formatPosition(start)} to ${formatPosition(end)} · ${formatLength(length)}`
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
    /** Opens on a part around the playback position, since that is what the viewer is looking at. */
    toggleClipPicker(): void {
      this.picking_clip = !this.picking_clip
      if (!this.picking_clip) {
        return
      }
      const start = Math.min(this.playbackPosition(), Math.max(this.duration - DEFAULT_CLIP_SECONDS, 0))
      this.clip_range = [start, Math.min(start + DEFAULT_CLIP_SECONDS, this.duration)]
    },
    onRangeInput(range: number[]): void {
      const [start, end] = this.clip_range
      this.moved_bound = Math.abs(range[0] - start) >= Math.abs(range[1] - end) ? 0 : 1
      this.clip_range = range
    },
    /** Shows the frame at the bound just dragged, once dragging stops: seeking on every step thrashes reads. */
    onRangeSettled(range: number[]): void {
      const [leader] = this.videos
      if (leader) {
        leader.currentTime = range[this.moved_bound]
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
    onExportError(error: unknown): void {
      this.error = error instanceof Error ? error.message : String(error)
    },
    onStats(stats: McapVideoStats): void {
      // Every stream reports the same figure, since they read the recording through one reader.
      this.bytes_downloaded = stats.bytesDownloaded
    },
  },
})
</script>

<style scoped>
.stream-grid {
  display: grid;
  gap: 12px;
}

.stream-grid.columns-2 {
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
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
</style>
