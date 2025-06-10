<template>
  <div />
</template>

<script lang="ts">
import Vue from 'vue'

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
  name: 'VideoDecoder',
  props: {
    videoData: {
      type: Uint8Array,
      required: true,
    },
    canvas: {
      type: [Object, HTMLCanvasElement],
      required: false,
      default: null,
    },
  },
  data() {
    return {
      decoder: null as VideoDecoder | null,
      framesDecoded: 0,
    }
  },
  watch: {
    videoData: {
      handler(newData: Uint8Array) {
        if (!newData || !this.decoder) {
          return
        }
        this.processVideoChunk(newData)
      },
      immediate: true,
    },
  },
  async mounted() {
    await this.setupVideoDecoder()
  },
  beforeDestroy() {
    this.cleanupVideoDecoder()
  },
  methods: {
    async setupVideoDecoder() {
      if (!this.canvas) {
        console.error('Canvas element not found')
        return
      }

      try {
        this.decoder = new window.VideoDecoder({
          output: (frame) => {
            this.renderFrame(frame)
            frame.close()
          },
          error: (error) => {
            console.error('VideoDecoder error:', error)
          },
        })

        // Configure decoder for H.264
        await this.decoder.configure({
          codec: 'avc1.42E01E',
          optimizeForLatency: true,
        })
      } catch (error) {
        console.error('Error setting up VideoDecoder:', error)
        this.decoder = null
      }
    },

    renderFrame(frame: VideoFrame) {
      if (!this.canvas) return

      const ctx = this.canvas.getContext('2d')
      if (!ctx) return

      // eslint-disable-next-line vue/no-mutating-props
      this.canvas.width = frame.displayWidth
      // eslint-disable-next-line vue/no-mutating-props
      this.canvas.height = frame.displayHeight
      ctx.drawImage(frame, 0, 0)
      this.framesDecoded += 1
      if (this.framesDecoded === 1) {
        this.$emit('frame-decoded')
      }
    },

    async processVideoChunk(chunkData: Uint8Array) {
      if (!this.decoder) {
        console.error('VideoDecoder not initialized')
        return
      }

      try {
        const chunk = new EncodedVideoChunk({
          type: 'key',
          data: chunkData,
          timestamp: 0,
          duration: 0,
        })
        this.decoder.decode(chunk)
      } catch (error) {
        console.error('Error decoding video chunk:', error)
      }
    },

    cleanupVideoDecoder() {
      if (this.decoder) {
        this.decoder.close()
      }
      this.decoder = null
      this.framesDecoded = 0
    },
  },
})
</script>
