<template>
  <div />
</template>

<script lang="ts">
import { FFmpeg } from '@ffmpeg/ffmpeg'
import { toBlobURL } from '@ffmpeg/util'
import Vue from 'vue'

export default Vue.extend({
  name: 'FFmpegDecoder',
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
      ffmpeg: null as FFmpeg | null,
      framesDecoded: 0,
      isFFmpegLoaded: false,
      isProcessing: false,
      videoChunks: [] as Uint8Array[],
      chunkCount: 0,
      finished: false,
      retryCount: 0,
      maxRetries: 3,
    }
  },
  watch: {
    videoData: {
      handler(newData: Uint8Array) {
        if (!newData || !this.ffmpeg || this.finished) {
          return
        }
        this.processVideoChunk(newData)
      },
      immediate: true,
    },
  },
  async mounted() {
    await this.loadFFmpeg()
  },
  beforeDestroy() {
    this.cleanupFFmpeg()
  },
  methods: {
    async loadFFmpeg() {
      if (this.isFFmpegLoaded) return

      try {
        await this.populateFFMPEG()
        this.isFFmpegLoaded = true
        this.retryCount = 0
      } catch (error) {
        console.error('Error loading FFmpeg:', error)
        throw error
      }
    },

    async processVideoChunk(chunkData: Uint8Array) {
      if (this.finished || !this.ffmpeg || this.isProcessing || !this.isFFmpegLoaded) {
        return
      }

      try {
        this.isProcessing = true

        this.videoChunks.push(new Uint8Array(chunkData))
        this.chunkCount += 1

        if (this.chunkCount % 50 === 0) {
          // limit videoChunks to prevent memory issues
          this.videoChunks = this.videoChunks.slice(-1200)

          // Combine chunks
          const totalLength = this.videoChunks.reduce((acc, chunk) => acc + chunk.length, 0)
          const combinedChunks = new Uint8Array(totalLength)
          let offset = 0
          for (const chunk of this.videoChunks) {
            combinedChunks.set(chunk, offset)
            offset += chunk.length
          }

          try {
            await this.cleanupFiles()
            await this.ffmpeg.writeFile('input.h264', combinedChunks)
            const return_code = await this.ffmpeg.exec(
              ['-f', 'h264', '-y', '-i', 'input.h264', '-frames:v', '1', 'frame.png'],
              5000,
            )

            if (return_code !== 0) {
              throw new Error('FFmpeg command failed')
            }

            // Read and render frame
            const frameData = await this.ffmpeg.readFile('frame.png') as Uint8Array
            const blob = new Blob([frameData], { type: 'image/png' })
            const url = URL.createObjectURL(blob)

            const img = new Image()
            img.onload = () => {
              if (this.canvas) {
                // clean the canvas first
                const ctx = this.canvas.getContext('2d')
                if (ctx) {
                  // eslint-disable-next-line vue/no-mutating-props
                  this.canvas.width = img.width
                  // eslint-disable-next-line vue/no-mutating-props
                  this.canvas.height = img.height
                  ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
                  ctx.drawImage(img, 0, 0)
                  this.finished = true
                  this.retryCount = 0
                  this.framesDecoded += 1
                  if (this.framesDecoded === 1) {
                    this.$emit('frame-decoded')
                  }
                }
              }
              URL.revokeObjectURL(url)
            }
            img.src = url
          } catch (error) {
            console.error('Error processing frame:', error)
            this.retryCount += 1

            if (this.retryCount >= this.maxRetries) {
              console.error('Max retries reached, restarting FFmpeg')
              await this.restartFFmpeg()
              this.retryCount = 0
            }
          } finally {
            await this.cleanupFiles()
          }
        }
      } catch (error) {
        console.error('Error in processVideoChunk:', error)
      } finally {
        this.isProcessing = false
      }
    },

    async cleanupFiles() {
      if (!this.ffmpeg) return

      try {
        await this.ffmpeg.deleteFile('input.h264')
        await this.ffmpeg.deleteFile('frame.png')
      } catch (error) {
        // Ignore cleanup errors
      }
    },

    async populateFFMPEG() {
      const baseURL = '/libs/ffmpeg'
      this.ffmpeg = new FFmpeg()
      await this.ffmpeg.load({
        coreURL: await toBlobURL(`${baseURL}/ffmpeg-core.js`, 'text/javascript'),
        wasmURL: await toBlobURL(`${baseURL}/ffmpeg-core.wasm`, 'application/wasm'),
      })
    },

    async restartFFmpeg() {
      try {
        await this.cleanupFiles()
        this.ffmpeg?.terminate()
        await this.populateFFMPEG()
      } catch (error) {
        console.error('Error restarting FFmpeg:', error)
        throw error
      }
    },

    cleanupFFmpeg() {
      this.cleanupFiles()
      this.ffmpeg?.terminate()
      this.ffmpeg = null
      this.framesDecoded = 0
      this.isFFmpegLoaded = false
      this.videoChunks = []
      this.chunkCount = 0
      this.finished = false
      this.retryCount = 0
    },
  },
})
</script>
