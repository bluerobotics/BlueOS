<template>
  <div>
    <div class="stream-wrapper">
      <video
        ref="player"
        autoplay
        muted
        playsinline
        class="stream"
      >
        <track
          kind="captions"
          srclang="en"
          label="Captions not available"
          :src="empty_captions"
          default
        >
      </video>
      <div v-if="!available && !error" class="stream-overlay">
        <span class="caption text-center white--text">Not available at this timestamp</span>
      </div>
      <div v-else-if="waiting && !error" class="stream-overlay stream-waiting">
        <span class="caption white--text">Waiting for new data...</span>
      </div>
      <div v-else-if="loading && !error" class="stream-overlay">
        <v-progress-circular indeterminate color="primary" size="40" />
        <span class="mt-2 caption white--text">{{ loading_message }}</span>
      </div>
      <div v-if="error" class="stream-overlay stream-error px-4">
        <v-icon color="error">
          mdi-alert-circle-outline
        </v-icon>
        <span class="mt-2 caption text-center white--text">{{ error }}</span>
      </div>
      <div v-if="statistics && !error" class="stats-overlay">
        <table class="grey--text text--lighten-3">
          <tbody>
            <tr v-for="row in detail_stat_rows" :key="row.label">
              <td class="stats-label">
                {{ row.label }}
              </td>
              <td :class="['stats-value', row.tone]">
                {{ row.value }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="stream-meta d-flex align-center caption mt-2 white--text">
      <v-icon x-small :color="error ? 'error' : 'success'" class="mr-1">
        mdi-circle
      </v-icon>
      <span class="font-weight-medium text-truncate">{{ track.name }}</span>
      <span v-if="resolution" class="ml-2 grey--text text--lighten-1">{{ resolution }}</span>
      <span v-if="codec_label" class="ml-2 grey--text text--lighten-1">{{ codec_label }}</span>
      <span v-if="frame_rate" class="ml-2 grey--text text--lighten-1">{{ frame_rate }}</span>
    </div>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import {
  McapVideoPlayer, McapVideoRecording, McapVideoStats,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'

interface StatRow {
  label: string
  value: string
  /** Vuetify text colour class, used to point out the counters that indicate trouble. */
  tone?: string
}

function share(value: number, total: number): string {
  return value > 0 && total > 0 ? ` (${(value / total * 100).toFixed(1)}%)` : ''
}

function prettifyBitrate(bitsPerSecond: number): string {
  if (bitsPerSecond >= 1e6) {
    return `${(bitsPerSecond / 1e6).toFixed(1)} Mbps`
  }
  return `${Math.round(bitsPerSecond / 1e3)} kbps`
}

/** Short codec family for the metadata row, e.g. avc1.640033 → H.264. */
function codecFamily(codec: string): string {
  if (codec.startsWith('avc1') || codec.startsWith('avc3')) {
    return 'H.264'
  }
  if (codec.startsWith('hvc1') || codec.startsWith('hev1')) {
    return 'H.265'
  }
  return codec
}

export default Vue.extend({
  name: 'McapVideoStream',
  props: {
    recording: {
      type: Object as PropType<McapVideoRecording>,
      required: true,
    },
    track: {
      type: Object as PropType<VideoTrack>,
      required: true,
    },
    statistics: {
      type: Boolean,
      default: false,
    },
    ongoing: {
      type: Boolean,
      default: false,
    },
    available: {
      type: Boolean,
      default: true,
    },
    position: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
      player: null as McapVideoPlayer | null,
      stats: {} as Partial<McapVideoStats>,
      error: null as string | null,
      loading: true,
      waiting: false,
      loading_message: this.ongoing ? 'Loading latest frame...' : 'Loading video...',
      empty_captions: 'data:text/vtt,WEBVTT',
    }
  },
  computed: {
    resolution(): string {
      const { width, height } = this.stats
      return width && height ? `${width}x${height}` : ''
    },
    codec_label(): string {
      return this.stats.codec ? codecFamily(this.stats.codec) : ''
    },
    frame_rate(): string {
      const { frameRate } = this.stats
      return frameRate && frameRate > 0 ? `${frameRate.toFixed(1)} fps` : ''
    },
    detail_stat_rows(): StatRow[] {
      const {
        framesRead = 0, keyframes = 0, framesLost = 0, framesSkipped = 0, framesCorrupt = 0,
        framesDecoded = 0, framesDropped = 0, decodeErrors = 0, frameRate = 0, bitrate = 0,
        bufferedAheadSeconds = 0, codec = '',
      } = this.stats
      return [
        { label: 'stream', value: [this.resolution, codec].filter((part) => part).join(' ') || '-' },
        { label: 'frames', value: `${framesRead} of ${this.track.frameCount} read` },
        { label: 'keyframes', value: `${keyframes}` },
        {
          label: 'lost',
          value: `${framesLost}${share(framesLost, framesRead + framesLost)}`,
          tone: framesLost > 0 ? 'warning--text' : undefined,
        },
        { label: 'skipped', value: `${framesSkipped}` },
        {
          label: 'corrupt',
          value: `${framesCorrupt}`,
          tone: framesCorrupt > 0 ? 'error--text' : undefined,
        },
        { label: 'decoded', value: `${framesDecoded}` },
        {
          label: 'dropped',
          value: `${framesDropped}${share(framesDropped, framesDecoded)}`,
          tone: framesDropped > 0 ? 'warning--text' : undefined,
        },
        {
          label: 'decode errors',
          value: `${decodeErrors}`,
          tone: decodeErrors > 0 ? 'error--text' : undefined,
        },
        { label: 'rate', value: `${frameRate.toFixed(1)} fps · ${prettifyBitrate(bitrate)}` },
        { label: 'buffered', value: `${bufferedAheadSeconds.toFixed(1)} s` },
      ]
    },
  },
  watch: {
    available(available: boolean) {
      if (available) {
        this.openPlayer()
      } else {
        this.closePlayer()
      }
    },
  },
  mounted() {
    const video = this.$refs.player as HTMLVideoElement
    video.addEventListener('timeupdate', this.onTimeUpdate)
    video.addEventListener('play', this.onPlay)
    video.addEventListener('pause', this.onPause)
    video.addEventListener('progress', this.onProgress)
    this.$emit('ready', video)
    if (this.available) {
      this.openPlayer()
    }
  },
  beforeDestroy() {
    const video = this.$refs.player as HTMLVideoElement
    video?.removeEventListener('timeupdate', this.onTimeUpdate)
    video?.removeEventListener('play', this.onPlay)
    video?.removeEventListener('pause', this.onPause)
    video?.removeEventListener('progress', this.onProgress)
    this.closePlayer()
  },
  methods: {
    openPlayer(): void {
      if (this.player) {
        this.player.seek(this.position)
        return
      }
      const video = this.$refs.player as HTMLVideoElement | undefined
      if (!video) {
        return
      }
      this.error = null
      this.loading = true
      this.player = new McapVideoPlayer(video, this.recording, this.track, {
        startSeconds: this.position,
        startAtEnd: this.ongoing,
        follow: this.ongoing,
        onStats: (stats) => {
          this.stats = stats
          this.loading = stats.loading
          this.waiting = stats.waiting
          this.$emit('stats', stats)
        },
        onError: (error) => {
          this.loading = false
          this.error = error.message
          this.$emit('error', error)
        },
        onExtended: () => this.$emit('extended'),
      })
      this.player.start().catch((error) => {
        this.loading = false
        this.error = error instanceof Error ? error.message : String(error)
      })
    },
    closePlayer(): void {
      this.player?.destroy()
      this.player = null
      this.loading = false
      this.waiting = false
    },
    onTimeUpdate(): void {
      const video = this.$refs.player as HTMLVideoElement
      this.$emit('timeupdate', video.currentTime)
    },
    onPlay(): void {
      this.$emit('play')
    },
    onPause(): void {
      if (!this.available) {
        return
      }
      if (this.ongoing && this.player?.wantPlaying) {
        return
      }
      this.$emit('pause')
    },
    onProgress(): void {
      this.$emit('progress')
    },
    // Used by the shared playback bar through $refs.
    // eslint-disable-next-line vue/no-unused-properties
    seek(seconds: number): void {
      if (!this.available) {
        return
      }
      this.player?.seek(seconds)
    },
    // eslint-disable-next-line vue/no-unused-properties
    play(): void {
      if (!this.available) {
        return
      }
      this.player?.setWantPlaying(true)
      const video = this.$refs.player as HTMLVideoElement
      video?.play().catch(() => undefined)
    },
    // eslint-disable-next-line vue/no-unused-properties
    pause(): void {
      this.player?.setWantPlaying(false)
      const video = this.$refs.player as HTMLVideoElement
      video?.pause()
    },
  },
})
</script>

<style scoped>
.stream-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  max-height: calc(72vh / var(--grid-rows, 1));
  background: #000;
}

.stream {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  background: #000;
}

.stream-overlay {
  position: absolute;
  inset: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.stream-error {
  background: rgba(0, 0, 0, 0.85);
}

.stream-waiting {
  justify-content: flex-end;
  padding-bottom: 12px;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.55));
}

.stream-meta {
  min-height: 20px;
  color: #e5e7eb;
}

.stats-overlay {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 2;
  max-width: calc(100% - 12px);
  padding: 8px 10px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.7);
  pointer-events: none;
}

.stats-overlay table {
  border-collapse: collapse;
  font-family: monospace;
  font-size: 11px;
  line-height: 1.35;
}

.stats-label {
  padding-right: 8px;
  opacity: 0.7;
  white-space: nowrap;
}

.stats-value {
  text-align: right;
  white-space: nowrap;
}
</style>
