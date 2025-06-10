<template>
  <div />
</template>

<script lang="ts">
import * as Broadway from 'broadway-player'
import Vue, { PropType } from 'vue'

interface BroadwayDecoder {
  decode(data: Uint8Array): void
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  onPictureDecoded?: (buffer: Uint8Array, width: number, height: number, _infos: any) => void
}

declare global {
  interface Window {
    Broadway: {
      Decoder: new () => BroadwayDecoder
    }
  }
}

export default Vue.extend({
  name: 'BroadwayVideoDecoder',
  props: {
    videoData: {
      type: Uint8Array,
      required: true,
    },
    canvas: {
      type: Object as PropType<HTMLCanvasElement | null>,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      broadwayDecoder: null as BroadwayDecoder | null,
      framesDecoded: 0,
    }
  },
  watch: {
    videoData: {
      handler(newData: Uint8Array) {
        if (!newData || !this.broadwayDecoder) {
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
        return
      }

      try {
        const decoder = new Broadway.Decoder()
        if (!decoder) {
          throw new Error('Failed to create Broadway decoder')
        }
        this.broadwayDecoder = decoder

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        this.broadwayDecoder.onPictureDecoded = (buffer: Uint8Array, width: number, height: number, _infos: any) => {
          this.renderYUVFrame(buffer, width, height)
          this.framesDecoded += 1
          if (this.framesDecoded === 1) {
            this.$emit('frame-decoded')
          }
        }
      } catch (error) {
        console.error('Error setting up Broadway decoder:', error)
        this.broadwayDecoder = null
      }
    },

    renderYUVFrame(buffer: Uint8Array, width: number, height: number) {
      if (!this.canvas) return

      const ctx = this.canvas.getContext('2d')
      if (!ctx) return

      // Set canvas dimensions to match the video frame
      // eslint-disable-next-line vue/no-mutating-props
      this.canvas.width = width
      // eslint-disable-next-line vue/no-mutating-props
      this.canvas.height = height

      const imageData = ctx.createImageData(width, height)
      const rgbData = imageData.data

      let yIndex = 0
      const uIndex = width * height
      const vIndex = uIndex + width * height / 4

      for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
          const pixelIndex = (y * width + x) * 4

          const yValue = buffer[yIndex]
          yIndex += 1
          const uValue = buffer[uIndex + Math.floor(y / 2) * Math.floor(width / 2) + Math.floor(x / 2)]
          const vValue = buffer[vIndex + Math.floor(y / 2) * Math.floor(width / 2) + Math.floor(x / 2)]

          const r = Math.max(0, Math.min(255, yValue + 1.402 * (vValue - 128)))
          const g = Math.max(0, Math.min(255, yValue - 0.344136 * (uValue - 128) - 0.714136 * (vValue - 128)))
          const b = Math.max(0, Math.min(255, yValue + 1.772 * (uValue - 128)))

          rgbData[pixelIndex] = r
          rgbData[pixelIndex + 1] = g
          rgbData[pixelIndex + 2] = b
          rgbData[pixelIndex + 3] = 255
        }
      }

      ctx.putImageData(imageData, 0, 0)
    },

    async processVideoChunk(chunkData: Uint8Array) {
      if (!this.broadwayDecoder) {
        console.error('Broadway decoder not initialized')
        return
      }

      try {
        this.broadwayDecoder.decode(chunkData)
      } catch (error) {
        console.error('Error decoding video chunk:', error)
      }
    },

    cleanupVideoDecoder() {
      this.broadwayDecoder = null
      this.framesDecoded = 0
    },
  },
})
</script>
