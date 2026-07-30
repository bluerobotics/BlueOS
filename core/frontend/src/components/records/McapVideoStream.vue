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
    </div>

    <div class="d-flex align-center caption grey--text text--darken-1 mt-1">
      <span class="font-weight-medium text-truncate">{{ track.name }}</span>
      <v-spacer />
      <span v-if="resolution" class="ml-3">{{ resolution }}</span>
      <span v-if="stats.codec" class="ml-3">{{ stats.codec }}</span>
    </div>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import {
  McapVideoPlayer, McapVideoRecording, McapVideoStats,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'

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
</style>
