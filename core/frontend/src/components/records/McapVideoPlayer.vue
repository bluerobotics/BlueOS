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

    <div class="player-wrapper">
      <video
        ref="player"
        controls
        autoplay
        class="player"
      >
        <track
          kind="captions"
          srclang="en"
          label="Captions not available"
          :src="empty_captions"
          default
        >
      </video>
      <div v-if="loading && !error" class="player-overlay">
        <v-progress-circular indeterminate color="primary" size="48" />
        <span class="mt-2 caption white--text">
          {{ loading_message }}
        </span>
      </div>
    </div>

    <div class="d-flex align-center flex-wrap mt-2">
      <v-select
        v-if="tracks.length > 1"
        v-model="selected_channel"
        :items="track_items"
        label="Video stream"
        dense
        hide-details
        outlined
        class="stream-select mr-4"
      />
      <div class="caption grey--text text--darken-1">
        <span v-if="resolution" class="mr-3">{{ resolution }}</span>
        <span v-if="stats.codec" class="mr-3">{{ stats.codec }}</span>
        <span
          v-tooltip="'Only the parts of the recording you watch are downloaded from the vehicle'"
          class="mr-3"
        >
          {{ downloaded }} downloaded
        </span>
        <span v-if="stats.bufferedAheadSeconds > 0">{{ stats.bufferedAheadSeconds.toFixed(1) }} s buffered</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import {
  isMediaSourceSupported,
  McapVideoPlayer,
  McapVideoRecording,
  McapVideoStats,
  openMcapVideoRecording,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'
import { prettifySize } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'McapVideoPlayer',
  props: {
    url: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      recording: null as McapVideoRecording | null,
      player: null as McapVideoPlayer | null,
      tracks: [] as VideoTrack[],
      selected_channel: null as number | null,
      stats: { bytesDownloaded: 0, bufferedAheadSeconds: 0 } as Partial<McapVideoStats>,
      error: null as string | null,
      loading: true,
      loading_message: 'Reading recording index...',
      empty_captions: 'data:text/vtt,WEBVTT',
    }
  },
  computed: {
    track_items(): { text: string, value: number }[] {
      return this.tracks.map((track) => ({ text: track.name, value: track.channelId }))
    },
    resolution(): string {
      const { width, height } = this.stats
      return width && height ? `${width}x${height}` : ''
    },
    downloaded(): string {
      return prettifySize((this.stats.bytesDownloaded ?? 0) / 1024)
    },
  },
  watch: {
    selected_channel(): void {
      this.startPlayback()
    },
  },
  async mounted() {
    if (!isMediaSourceSupported()) {
      this.error = 'This browser cannot play recordings, as it does not support Media Source Extensions.'
      this.loading = false
      return
    }
    await this.openRecording()
  },
  beforeDestroy() {
    this.player?.destroy()
  },
  methods: {
    async openRecording(): Promise<void> {
      try {
        this.recording = await openMcapVideoRecording(this.url)
        this.tracks = this.recording.tracks
        if (this.tracks.length === 0) {
          this.error = 'This recording does not contain any video stream.'
          this.loading = false
          return
        }
        // Selecting the channel triggers playback through its watcher
        const [main_track] = [...this.tracks].sort((left, right) => right.frameCount - left.frameCount)
        this.selected_channel = main_track.channelId
      } catch (error) {
        this.reportError(error)
      }
    },
    startPlayback(): void {
      const track = this.tracks.find((item) => item.channelId === this.selected_channel)
      if (!this.recording || !track) {
        return
      }

      this.player?.destroy()
      this.loading = true
      this.loading_message = 'Looking for a keyframe...'
      this.error = null

      const video = this.$refs.player as HTMLVideoElement
      this.player = new McapVideoPlayer(video, this.recording, track, {
        onStats: (stats) => {
          this.stats = stats
          this.loading = stats.loading
        },
        onError: (error) => this.reportError(error),
      })
      this.player.start().catch((error) => this.reportError(error))
    },
    reportError(error: unknown): void {
      this.loading = false
      this.error = error instanceof Error ? error.message : String(error)
    },
  },
})
</script>

<style scoped>
.player-wrapper {
  position: relative;
  width: 100%;
  padding-top: 56.25%;
  background: #111827;
}

.player {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.player-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.stream-select {
  max-width: 260px;
}
</style>
