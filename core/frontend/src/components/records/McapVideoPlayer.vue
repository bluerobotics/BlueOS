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
        :controls="index === 0"
        @ready="onStreamReady(index, $event)"
        @stats="onStats"
      />
    </div>

    <div v-if="bytes_downloaded > 0" class="caption grey--text text--darken-1 mt-2">
      <span
        v-tooltip="'Only the parts of the recording you watch are downloaded from the vehicle'"
        class="mr-3"
      >
        {{ downloaded }} downloaded
      </span>
      <span v-if="tracks.length > 1">
        {{ tracks.length }} streams playing together, sharing the same download
      </span>
    </div>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import McapVideoStream from '@/components/records/McapVideoStream.vue'
import {
  isMediaSourceSupported, McapVideoRecording, McapVideoStats, openMcapVideoRecording,
} from '@/libs/mcap/player'
import { VideoTrack } from '@/libs/mcap/video-track'
import { prettifySize } from '@/utils/helper_functions'

/** How far a stream may drift from the one being controlled before it is nudged back into place. */
const SYNC_TOLERANCE_SECONDS = 0.5
/** `HTMLMediaElement.HAVE_CURRENT_DATA`: the element has a frame for its current position. */
const HAVE_CURRENT_DATA = 2

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
    }
  },
  computed: {
    columns(): number {
      return Math.min(this.tracks.length, 2)
    },
    downloaded(): string {
      return prettifySize(this.bytes_downloaded / 1024)
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
</style>
