<template>
  <div>
    <div style="position: relative;">
      <div style="margin-bottom: 10px; margin-top: 10px;">
        <v-select
          v-model="selectedDecoder"
          :items="decoderOptions"
          label="Select Decoder"
          outlined
          dense
          hide-details
          style="max-width: 200px;"
        />
      </div>
      <canvas
        ref="videoCanvas"
        style="width: 100%; height: auto; background: #000;"
      />
      <div v-if="isLoading" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);">
        <spinning-logo
          size="50"
          :subtitle="loadingMessage"
        />
      </div>
    </div>
    <template v-if="videoCanvas">
      <component
        :is="currentDecoder"
        :key="selectedDecoder"
        :video-data="videoData"
        :canvas="videoCanvas"
        @frame-decoded="onFrameDecoded"
      />
    </template>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'

import BroadwayVideoDecoder from './BroadwayVideoDecoder.vue'
import FFmpegDecoder from './FFmpegDecoder.vue'
import VideoDecoder from './VideoDecoder.vue'

interface VideoDecoderConfig {
  codec: string
  optimizeForLatency: boolean
}

interface VideoDecoderInit {
  output: (frame: VideoFrame) => void
  error: (error: Error) => void
}

declare global {
  interface Window {
    VideoDecoder: {
      new (init: VideoDecoderInit): {
        configure: (config: VideoDecoderConfig) => Promise<void>
        decode: (chunk: EncodedVideoChunk) => void
        close: () => void
        decodeQueueSize: number
        ondequeue: ((event: Event) => void) | null
        state: 'unconfigured' | 'configured' | 'closed'
        flush: () => Promise<void>
        reset: () => void
        addEventListener: (type: string, listener: EventListenerOrEventListenerObject) => void
        removeEventListener: (type: string, listener: EventListenerOrEventListenerObject) => void
        dispatchEvent: (event: Event) => boolean
      }
    }
  }
}

export default Vue.extend({
  name: 'RawVideoPlayer',
  components: {
    BroadwayVideoDecoder,
    VideoDecoder,
    FFmpegDecoder,
    SpinningLogo,
  },
  props: {
    videoData: {
      type: Uint8Array,
      required: true,
    },
  },
  data() {
    return {
      hasDecodedFrame: false,
      videoCanvas: null as HTMLCanvasElement | null,
      selectedDecoder: 'ffmpeg',
    }
  },
  computed: {
    allowHardwareDecoding(): boolean {
      const { isSecureContext } = window
      const { hostname } = window.location
      const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1'
      return isLocalhost || isSecureContext
    },
    decoderOptions() {
      const options = [
        { text: 'FFmpeg Decoder', value: 'ffmpeg' },
        { text: 'Broadway Decoder', value: 'broadway' },
      ]
      if (this.allowHardwareDecoding) {
        options.push({ text: 'Hardware Decoder', value: 'video' })
      }
      return options
    },
    isLoading(): boolean {
      return !this.hasDecodedFrame
    },
    loadingMessage(): string {
      return 'Waiting for first frame...'
    },
    currentDecoder(): string {
      switch (this.selectedDecoder) {
        case 'broadway':
          return 'BroadwayVideoDecoder'
        case 'ffmpeg':
          return 'FFmpegDecoder'
        case 'video':
          return 'VideoDecoder'
        default:
          if (this.allowHardwareDecoding) {
            return 'VideoDecoder'
          }
          return 'FFmpegDecoder'
      }
    },
  },
  watch: {
    selectedDecoder(_newVal) {
      this.hasDecodedFrame = false
      // make canvas black
      if (this.videoCanvas) {
        const ctx = this.videoCanvas.getContext('2d')
        if (ctx) {
          ctx.fillStyle = '#000'
          ctx.fillRect(0, 0, this.videoCanvas.width, this.videoCanvas.height)
        }
      }
      // Force component re-render
      this.$nextTick(() => {
        this.videoCanvas = null
        this.$nextTick(() => {
          this.videoCanvas = this.$refs.videoCanvas as HTMLCanvasElement
        })
      })
    },
  },
  mounted() {
    this.videoCanvas = this.$refs.videoCanvas as HTMLCanvasElement
    this.selectedDecoder = this.allowHardwareDecoding ? 'video' : 'ffmpeg'
  },
  methods: {
    onFrameDecoded() {
      this.hasDecodedFrame = true
    },
  },
})
</script>
