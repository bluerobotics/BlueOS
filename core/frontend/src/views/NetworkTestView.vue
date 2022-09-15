<template>
  <v-container
    class="d-flex justify-center fluid"
  >
    <v-card>
      <v-card-title class="justify-center">
        Local Network speed and latency tests
      </v-card-title>

      <v-divider />

      <v-col>
        <v-col
          class="d-flex justify-center"
        >
          <v-progress-circular
            :rotate="90"
            :width="15"
            :value="speed * 100 / max_speed"
            ratio="1"
            color="primary"
            size="200"
          >
            {{ speed.toFixed(2) }} Mbps
          </v-progress-circular>

          <v-list>
            <v-list-item>
              <v-list-item-icon>
                <v-icon
                  v-tooltip="'Download speed'"
                >
                  mdi-download
                </v-icon>
              </v-list-item-icon>
              <v-list-item-subtitle>
                {{ download_speed ? download_speed.toFixed(2) : '...' }} Mbps
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon
                  v-tooltip="'Upload speed'"
                >
                  mdi-upload
                </v-icon>
              </v-list-item-icon>
              <v-list-item-subtitle>
                {{ upload_speed ? upload_speed.toFixed(2) : '...' }} Mbps
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon
                  v-tooltip="'Latency'"
                >
                  mdi-timer-outline
                </v-icon>
              </v-list-item-icon>
              <v-list-item-subtitle>
                {{ latency_ms ? latency_ms.toFixed(0) : '...' }} ms
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-col>
        <div
          class="transition-swing pa-6"
          align="center"
          v-text="state"
        />
        <v-alert
          v-if="result"
          dense
          align-center
          justify-center
          flex-wrap
          :type="result.type"
        >
          {{ result.message }}
        </v-alert>
        <v-card-actions class="justify-center">
          <v-btn
            color="primary"
            :disabled="!allow_test_start"
            @click="start()"
          >
            <v-icon>
              mdi-play
            </v-icon>
          </v-btn>
        </v-card-actions>
      </v-col>
    </v-card>
  </v-container>
</template>

<script lang="ts">
import { differenceInMilliseconds } from 'date-fns'
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { network_speed_test_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(network_speed_test_service)

enum State {
  None = 'Click to start',
  DownloadSpeed = 'Downloading from vehicle..',
  UploadSpeed = 'Uploading to vehicle..',
  Done = 'Test done',
}

interface NetworkTestResult {
  type: string;
  message: string;
}

export default Vue.extend({
  name: 'NetworkTestView',
  components: {
  },
  data() {
    return {
      max_speed: 100,
      state: State.None,
      result: undefined as NetworkTestResult | undefined,
      speed: 0,
      download_speed: undefined as number | undefined,
      upload_speed: undefined as number | undefined,
      latency_ms: undefined as number | undefined,
      websocket: undefined as WebSocket | undefined,
      upload_buffer: new ArrayBuffer(100 * 2 ** 20), // Generate 100MB buffer only once
      interval: 0,
    }
  },
  computed: {
    allow_test_start(): boolean {
      return [State.None, State.Done].includes(this.state)
    },
  },
  beforeDestroy() {
    clearInterval(this.interval)
    this.websocket?.close()
  },
  mounted() {
    this.openWebSocket()
  },
  methods: {
    openWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      this.websocket = new WebSocket(`${protocol}://${window.location.host}/network-test/ws`)
      this.websocket.onmessage = (message: MessageEvent): void => {
        this.latency_ms = window.performance.now() - parseInt(message.data, 10)
      }
      this.websocket.onerror = () => {
        this.latency_ms = -1
      }

      this.interval = setInterval(() => {
        if (this.websocket === undefined || this.websocket?.readyState === WebSocket.CLOSED) {
          this.openWebSocket()
        }

        if (this.websocket?.readyState === WebSocket.OPEN) {
          this.websocket?.send(window.performance.now().toString())
        }
      }, 200)
    },
    start(): void {
      this.updateState(State.DownloadSpeed)
    },
    clearSpeed(): void {
      this.speed = 0
      this.max_speed = 100
    },
    setSpeed(speed: number): void {
      if (speed > this.max_speed) {
        this.max_speed = speed
      }
      this.speed = speed
    },
    updateState(state: State): void {
      this.state = state
      switch (this.state) {
        case State.DownloadSpeed:
          this.clearSpeed()
          this.checkDownloadSpeed()
          break
        case State.UploadSpeed:
          this.clearSpeed()
          this.checkUploadSpeed()
          break
        case State.Done:
          if (this.download_speed === undefined || this.upload_speed === undefined) {
            break
          }

          if (this.download_speed >= 40 && this.upload_speed >= 40) {
            this.result = {
              type: 'success',
              message: 'Great upload and download speed.',
            }
          } else if (this.download_speed < 40 && this.upload_speed < 40) {
            this.result = {
              type: 'error',
              message: 'Download and upload speed are below threshold, check your hardware interface.',
            }
          } else if (this.upload_speed < 40) {
            this.result = {
              type: 'warning',
              message: 'Upload speed below threshold, video may contain artifacts, check your hardware interface.',
            }
          } else if (this.download_speed < 40) {
            this.result = {
              type: 'warning',
              message: 'Download speed below threshold, connection may be unstable, check your hardware interface.',
            }
          }
          break
        default:
          break
      }
    },
    checkUploadSpeed(): void {
      let start_time: number

      back_axios({
        method: 'post',
        url: '/network-test/post_file',
        timeout: 20000,
        data: this.upload_buffer,
        onUploadProgress: (progress_event) => {
          if (start_time === undefined) {
            start_time = new Date().getTime()
            return
          }
          const seconds = differenceInMilliseconds(new Date().getTime(), start_time) * 1e-3
          const speed_Mb = 8 * (progress_event.loaded / seconds / 2 ** 20)
          const alpha_factor = 0.7
          this.upload_speed = (this.upload_speed ?? 0) * (1 - alpha_factor) + alpha_factor * speed_Mb
          const percentage = 100 * (progress_event.loaded / progress_event.total)
          console.debug(
            `network-test: Upload: ${speed_Mb.toFixed(2)}Mbps ${percentage.toFixed(2)}% ${seconds.toFixed(2)}s`,
          )
          this.setSpeed(speed_Mb)
        },
      }).catch((error) => {
        const message = `Failed to do speed test: ${error.message}`
        notifier.pushError('NETWORK_SPEED_TEST_UPLOAD', message)
        console.error(message)
      }).finally(() => this.updateState(State.Done))
    },
    checkDownloadSpeed(): void {
      const one_hundred_mega_bytes = 100 * 2 ** 20
      let start_time: number

      back_axios({
        method: 'get',
        url: '/network-test/get_file',
        timeout: 20000,
        data: {
          size: one_hundred_mega_bytes,
          avoid_cache: new Date().getTime(),
        },
        onDownloadProgress: (progress_event) => {
          if (start_time === undefined) {
            start_time = new Date().getTime()
            return
          }
          const seconds = differenceInMilliseconds(new Date().getTime(), start_time) * 1e-3
          const speed_Mb = 8 * (progress_event.loaded / seconds / 2 ** 20)
          const alpha_factor = 0.7
          this.download_speed = (this.download_speed ?? 0) * (1 - alpha_factor) + alpha_factor * speed_Mb
          const percentage = 100 * (progress_event.loaded / progress_event.total)
          console.debug(
            `network-test: Download: ${speed_Mb.toFixed(2)}Mbps ${percentage.toFixed(2)}% ${seconds.toFixed(2)}s`,
          )
          this.setSpeed(speed_Mb)
        },
      }).catch((error) => {
        const message = `Failed to do speed test: ${error.message}`
        notifier.pushError('NETWORK_SPEED_TEST_DOWNLOAD', message)
        console.error(message)
      }).finally(() => this.updateState(State.UploadSpeed))
    },
  },
})
</script>
