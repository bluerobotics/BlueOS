<template>
  <div>
    <div class="stream-wrapper">
      <video
        ref="player"
        :controls="controls"
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
      <div v-if="loading && !error" class="stream-overlay">
        <v-progress-circular indeterminate color="primary" size="40" />
        <span class="mt-2 caption white--text">{{ loading_message }}</span>
      </div>
      <div v-if="error" class="stream-overlay stream-error px-4">
        <v-icon color="error">
          mdi-alert-circle-outline
        </v-icon>
        <span class="mt-2 caption text-center white--text">{{ error }}</span>
      </div>
      <table v-if="statistics && !error" class="stats-overlay grey--text text--lighten-3">
        <tr v-for="row in detail_stat_rows" :key="row.label">
          <td class="stats-label">
            {{ row.label }}
          </td>
          <td :class="['stats-value', row.tone]">
            {{ row.value }}
          </td>
        </tr>
      </table>
    </div>

    <div class="stream-meta d-flex align-center caption mt-2">
      <v-icon x-small :color="error ? 'error' : 'success'" class="mr-1">
        mdi-circle
      </v-icon>
      <span class="font-weight-medium text-truncate">{{ track.name }}</span>
      <span v-if="resolution" class="ml-2 grey--text text--darken-1">{{ resolution }}</span>
      <span v-if="codec_label" class="ml-2 grey--text text--darken-1">{{ codec_label }}</span>
      <span v-if="frame_rate" class="ml-2 grey--text text--darken-1">{{ frame_rate }}</span>
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
    controls: {
      type: Boolean,
      default: false,
    },
    statistics: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      player: null as McapVideoPlayer | null,
      stats: {} as Partial<McapVideoStats>,
      error: null as string | null,
      loading: true,
      loading_message: 'Loading video...',
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
  mounted() {
    const video = this.$refs.player as HTMLVideoElement
    this.player = new McapVideoPlayer(video, this.recording, this.track, {
      onStats: (stats) => {
        this.stats = stats
        this.loading = stats.loading
        this.$emit('stats', stats)
      },
      onError: (error) => {
        this.loading = false
        this.error = error.message
        this.$emit('error', error)
      },
    })
    this.player.start().catch((error) => {
      this.loading = false
      this.error = error instanceof Error ? error.message : String(error)
    })
    this.$emit('ready', video)
  },
  beforeDestroy() {
    this.player?.destroy()
  },
})
</script>

<style scoped>
.stream-wrapper {
  position: relative;
  width: 100%;
  padding-top: 56.25%;
  background: #111827;
}

.stream {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.stream-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.stream-error {
  background: rgba(17, 24, 39, 0.85);
}

.stream-meta {
  min-height: 20px;
}

.stats-overlay {
  position: absolute;
  top: 6px;
  left: 6px;
  max-width: calc(100% - 12px);
  border-collapse: collapse;
  background: rgba(17, 24, 39, 0.7);
  border-radius: 4px;
  padding: 4px 6px;
  font-family: monospace;
  font-size: 11px;
  line-height: 1.35;
  pointer-events: none;
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
