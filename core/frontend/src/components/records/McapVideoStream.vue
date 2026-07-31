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
        <tr v-for="row in stat_rows" :key="row.label">
          <td class="stats-label">
            {{ row.label }}
          </td>
          <td :class="['stats-value', row.tone]">
            {{ row.value }}
          </td>
        </tr>
      </table>
    </div>

    <v-progress-linear
      v-if="export_progress"
      :value="export_percentage"
      height="3"
      color="primary"
    />

    <div class="d-flex align-center caption grey--text text--darken-1 mt-1">
      <span class="font-weight-medium text-truncate">{{ track.name }}</span>
      <v-spacer />
      <template v-if="export_progress">
        <span>saving {{ export_percentage }}% · {{ export_size }}</span>
        <v-btn
          v-tooltip="'Stop saving'"
          icon
          x-small
          class="ml-1"
          @click="cancelExport"
        >
          <v-icon small>
            mdi-close
          </v-icon>
        </v-btn>
      </template>
      <template v-else>
        <span v-if="resolution" class="ml-3">{{ resolution }}</span>
        <span v-if="stats.codec" class="ml-3">{{ stats.codec }}</span>
        <v-btn
          v-if="!error"
          v-tooltip="'Save this stream as an MP4 file'"
          icon
          x-small
          class="ml-2"
          @click="saveMp4"
        >
          <v-icon small>
            mdi-download
          </v-icon>
        </v-btn>
      </template>
    </div>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { exportTrackAsMp4, Mp4ExportProgress, saveBlob } from '@/libs/mcap/export'
import {
  McapVideoPlayer, McapVideoRecording, McapVideoStats,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'
import { prettifySize } from '@/utils/helper_functions'

/** Time between progress updates, so that saving does not repaint the page on every frame. */
const PROGRESS_INTERVAL_MS = 200

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
    name: {
      type: String,
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
      export_progress: null as Mp4ExportProgress | null,
      export_controller: null as AbortController | null,
      last_progress_at: 0,
    }
  },
  computed: {
    resolution(): string {
      const { width, height } = this.stats
      return width && height ? `${width}x${height}` : ''
    },
    export_percentage(): number {
      const { seconds, durationSeconds } = this.export_progress ?? { seconds: 0, durationSeconds: 0 }
      return durationSeconds > 0 ? Math.min(100, Math.round(seconds / durationSeconds * 100)) : 0
    },
    export_size(): string {
      return prettifySize((this.export_progress?.bytes ?? 0) / 1024)
    },
    stat_rows(): StatRow[] {
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
    this.export_controller?.abort()
  },
  methods: {
    async saveMp4(): Promise<void> {
      const controller = new AbortController()
      this.export_controller = controller
      this.export_progress = { seconds: 0, durationSeconds: this.recording.durationSeconds, bytes: 0 }
      try {
        const file = await exportTrackAsMp4(this.recording, this.track, {
          signal: controller.signal,
          onProgress: (progress) => {
            const now = Date.now()
            if (now - this.last_progress_at >= PROGRESS_INTERVAL_MS) {
              this.last_progress_at = now
              this.export_progress = progress
            }
          },
        })
        saveBlob(file, `${this.name}-${this.track.name}.mp4`)
      } catch (error) {
        if (!(error instanceof Error) || error.name !== 'AbortError') {
          this.$emit('export-error', error)
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
