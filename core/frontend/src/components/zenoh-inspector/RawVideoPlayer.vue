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
    <div class="stream-wrapper">
      <video
        v-show="path === 'mse'"
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
      <canvas
        v-show="path === 'webcodecs'"
        ref="canvas"
        class="stream"
      />
      <div v-if="loading && !error" class="stream-overlay">
        <v-progress-circular
          indeterminate
          color="primary"
          size="40"
        />
        <span class="mt-2 caption white--text">Waiting for first frame...</span>
      </div>
    </div>
    <div
      v-if="!error"
      class="stream-meta d-flex align-center caption mt-2 white--text"
    >
      <v-icon
        x-small
        :color="loading ? 'grey' : 'success'"
        class="mr-1"
      >
        mdi-circle
      </v-icon>
      <span v-if="resolution">{{ resolution }}</span>
      <span v-if="codec_label" class="ml-2 grey--text text--lighten-1">{{ codec_label }}</span>
      <span v-if="path_label" class="ml-2 grey--text text--lighten-1">{{ path_label }}</span>
      <span
        v-if="lag_label"
        :class="['ml-2', lag_warning ? 'warning--text' : 'grey--text text--lighten-1']"
      >
        lag {{ lag_label }}
      </span>
    </div>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import { AnnexBMsePlayer, AnnexBMseStats } from '@/libs/mcap/annexb-player'
import { AnnexBWebCodecsPlayer, isWebCodecsSupported } from '@/libs/mcap/annexb-webcodecs-player'
import { VideoFormat } from '@/libs/mcap/codec'
import { isMediaSourceSupported } from '@/libs/mcap/mse'

function codecFamily(codec: string): string {
  if (codec.startsWith('avc1') || codec.startsWith('avc3')) {
    return 'H.264'
  }
  if (codec.startsWith('hvc1') || codec.startsWith('hev1')) {
    return 'H.265'
  }
  return codec
}

type LivePath = 'webcodecs' | 'mse' | ''

type LivePlayer = {
  push: (data: Uint8Array, format: VideoFormat, timestampSeconds?: number) => void
  destroy: () => void
}

export default Vue.extend({
  name: 'RawVideoPlayer',
  data() {
    return {
      player: null as LivePlayer | null,
      stats: null as AnnexBMseStats | null,
      error: null as string | null,
      loading: true,
      path: '' as LivePath,
      empty_captions: 'data:text/vtt,WEBVTT',
    }
  },
  computed: {
    resolution(): string {
      const width = this.stats?.width
      const height = this.stats?.height
      return width && height ? `${width}x${height}` : ''
    },
    codec_label(): string {
      return this.stats?.codec ? codecFamily(this.stats.codec) : ''
    },
    path_label(): string {
      if (this.path === 'webcodecs') {
        return 'WebCodecs'
      }
      if (this.path === 'mse') {
        return 'MSE'
      }
      return ''
    },
    lag_label(): string {
      if (!this.stats) {
        return ''
      }
      return `${Math.round(this.stats.lagSeconds * 1000)} ms`
    },
    lag_warning(): boolean {
      return (this.stats?.lagSeconds ?? 0) > 0.5
    },
  },
  mounted() {
    this.startPreferredPlayer()
  },
  beforeDestroy() {
    this.player?.destroy()
    this.player = null
  },
  methods: {
    playerOptions(fallbackToMse: boolean) {
      return {
        onReady: () => {
          this.loading = false
        },
        onError: (error: Error) => {
          if (fallbackToMse && this.path === 'webcodecs' && isMediaSourceSupported()) {
            this.startMsePlayer()
            return
          }
          this.loading = false
          this.error = error.message
        },
        onStats: (stats: AnnexBMseStats) => {
          this.stats = stats
        },
      }
    },
    startPreferredPlayer(): void {
      if (isWebCodecsSupported()) {
        this.startWebCodecsPlayer()
        return
      }
      this.startMsePlayer()
    },
    startWebCodecsPlayer(): void {
      const canvas = this.$refs.canvas as HTMLCanvasElement
      this.player?.destroy()
      this.player = new AnnexBWebCodecsPlayer(canvas, this.playerOptions(true))
      this.path = 'webcodecs'
    },
    startMsePlayer(): void {
      const video = this.$refs.player as HTMLVideoElement
      if (!isMediaSourceSupported()) {
        this.error = 'This browser cannot play video, as it does not support Media Source Extensions.'
        this.loading = false
        return
      }
      this.player?.destroy()
      try {
        this.player = new AnnexBMsePlayer(video, this.playerOptions(false))
        this.path = 'mse'
      } catch (error) {
        this.loading = false
        this.error = error instanceof Error ? error.message : String(error)
      }
    },
    // Used by ZenohInspector through $refs so frames are not dropped by Vue's update batching.
    // eslint-disable-next-line vue/no-unused-properties
    pushFrame(data: Uint8Array, format: VideoFormat, timestampSeconds?: number): void {
      this.player?.push(data, format, timestampSeconds)
    },
  },
})
</script>

<style scoped>
.stream-wrapper {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
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
  object-fit: contain;
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

.stream-meta {
  min-height: 20px;
  color: #e5e7eb;
}
</style>
