<template>
  <v-container
    class="d-flex flex-row align-center justify-center fluid"
  >
    <v-card max-width="390px">
      <v-card-title class="justify-center">
        Internet Speed and Latency Test
        <v-overlay
          width="100%"
          absolute
          opacity="0.92"
          :value="!helper.has_internet"
        >
          Waiting for internet connection..
        </v-overlay>
      </v-card-title>

      <v-divider />

      <v-col>
        <v-col
          class="d-flex justify-center"
        >
          <v-list>
            <v-list-item>
              <v-list-item-icon>
                <v-icon
                  v-tooltip="'Server to test internet speed'"
                >
                  mdi-server-network
                </v-icon>
              </v-list-item-icon>
              <v-list-item-subtitle>
                {{ server_origin }}
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon
                  v-tooltip="'Client provider'"
                >
                  mdi-home-circle-outline
                </v-icon>
              </v-list-item-icon>
              <v-list-item-subtitle>
                {{ client_origin }}
                <v-list-item-icon
                  v-if="client_isp_rating"
                  v-tooltip="'Provider ISP rating'"
                >
                  (
                  <div>
                    <v-icon
                      v-for="index in 5"
                      :key="index"
                      size="small"
                    >
                      {{ getRateIcon(index, client_isp_rating) }}
                    </v-icon>
                  </div>
                  )
                </v-list-item-icon>
              </v-list-item-subtitle>
            </v-list-item>

            <v-list-item>
              <v-list-item-icon>
                <v-icon
                  v-tooltip="'Download speed from internet'"
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
                  v-tooltip="'Upload speed to internet'"
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
        <p class="text-center">
          {{ message }}
        </p>
        <v-card-actions class="justify-center">
          <v-btn
            color="primary"
            :disabled="started"
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
import Vue from 'vue'

import helper from '@/store/helper'
import { SpeedTestResult } from '@/types/helper'

export default Vue.extend({
  name: 'InternetSpeedTest',
  data() {
    return {
      helper,
      result: undefined as SpeedTestResult | undefined,
      started: false,
      message: undefined as string | undefined,
    }
  },
  computed: {
    client_origin(): string {
      return this.result?.client.isp ?? '...'
    },
    client_isp_rating(): number {
      const rating = this.result?.client.isprating ?? '0'
      return parseFloat(rating)
    },
    server_origin(): string {
      const server = this.result?.server
      if (server) {
        return `${server.country} - ${server.name}`
      }
      return '...'
    },
    download_speed(): number | undefined {
      const value = this.result?.download
      if (value) {
        return value / 2 ** 20
      }
      return undefined
    },
    upload_speed(): number | undefined {
      const value = this.result?.upload
      if (value) {
        return value / 2 ** 20
      }
      return undefined
    },
    latency_ms(): number | undefined {
      return this.result?.ping
    },
  },
  async mounted() {
    this.result = await helper.checkPreviousInternetTestResult() ?? undefined
  },
  methods: {
    getRateIcon(index: number, rate: number): string {
      if (index <= rate) {
        return 'mdi-star'
      }

      if (index > rate && rate > index - 1) {
        return 'mdi-star-half-full'
      }

      return 'mdi-star-outline'
    },
    async start(): Promise<void> {
      this.result = undefined
      this.started = true
      this.message = 'Starting.. Looking for best server..'
      this.result = await helper.checkInternetBestServer() ?? this.result
      this.message = 'Checking download speed..'
      this.result = await helper.checkInternetDownloadSpeed() ?? this.result
      this.message = 'Checking upload speed..'
      this.result = await helper.checkInternetUploadSpeed() ?? this.result
      this.message = 'Done!'
      this.started = false
    },
  },
})
</script>
