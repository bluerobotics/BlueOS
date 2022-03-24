<template>
  <v-container
    class="d-flex justify-center fluid"
  >
    <v-card>
      <v-card-title class="justify-center">
        Network speed and latency test
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
            color="blue"
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
                {{ latency_us ? latency_us.toFixed(0) : '...' }} us
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
        </v-col>
        <div
          class="transition-swing pa-6"
          align="center"
          v-text="state"
        />
        <v-card-actions class="justify-center">
          <v-btn
            :disabled="!allow_test_start"
            @click="start()"
          >
            <v-icon color="green">
              mdi-play
            </v-icon>
          </v-btn>
        </v-card-actions>
      </v-col>
    </v-card>
  </v-container>
</template>

<script lang="ts">
import { differenceInSeconds } from 'date-fns'
import Vue from 'vue'

import notifications from '@/store/notifications'
import { network_speed_test_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

enum State {
  None = 'Click to start',
  DownloadSpeed = 'Testing download speed',
  UploadSpeed = 'Testing upload speed',
  Done = 'Test done',
}

export default Vue.extend({
  name: 'NetworkTestView',
  components: {
  },
  data() {
    return {
      max_speed: 100,
      state: State.None,
      speed: 0,
      download_speed: undefined as number | undefined,
      upload_speed: undefined as number | undefined,
      latency_us: undefined as number | undefined,
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
        this.latency_us = window.performance.now() - parseInt(message.data, 10)
      }
      this.websocket.onerror = () => {
        this.latency_us = -1
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
        default:
          break
      }
    },
    async checkUploadSpeed(): Promise<void> {
      let start_time: number

      await back_axios({
        method: 'post',
        url: '/network-test/post_file',
        timeout: 20000,
        data: this.upload_buffer,
        onUploadProgress: (progress_event) => {
          if (start_time === undefined) {
            start_time = new Date().getTime()
            return
          }
          const seconds = differenceInSeconds(new Date().getTime(), start_time)
          // Avoid huge speeds on start
          if (seconds < 2) {
            return
          }
          const speed_Mb = 8 * (progress_event.loaded / seconds / 2 ** 20)
          this.upload_speed = speed_Mb
          const percentage = 100 * (progress_event.loaded / progress_event.total)
          console.debug(
            `network-test: Upload: ${speed_Mb.toFixed(2)}Mbps ${percentage.toFixed(2)}% ${seconds.toFixed(2)}s`,
          )
          this.setSpeed(speed_Mb)
        },
      }).catch((error) => {
        const message = `Failed to do speed test: ${error.message}`
        notifications.pushError({ service: network_speed_test_service, type: 'NETWORK_SPEED_TEST_UPLOAD', message })
        console.error(message)
      })

      this.updateState(State.Done)
    },
    async checkDownloadSpeed(): Promise<void> {
      const one_hundred_mega_bytes = 100 * 2 ** 20
      let start_time: number

      await back_axios({
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
          const seconds = differenceInSeconds(new Date().getTime(), start_time)
          // Avoid huge speeds on start
          if (seconds < 2) {
            return
          }
          const speed_Mb = 8 * (progress_event.loaded / seconds / 2 ** 20)
          this.download_speed = speed_Mb
          const percentage = 100 * (progress_event.loaded / progress_event.total)
          console.debug(
            `network-test: Download: ${speed_Mb.toFixed(2)}Mbps ${percentage.toFixed(2)}% ${seconds.toFixed(2)}s`,
          )
          this.setSpeed(speed_Mb)
        },
      }).catch((error) => {
        const message = `Failed to do speed test: ${error.message}`
        notifications.pushError({ service: network_speed_test_service, type: 'NETWORK_SPEED_TEST_DOWNLOAD', message })
        console.error(message)
      })

      this.updateState(State.UploadSpeed)
    },
  },
})
</script>
