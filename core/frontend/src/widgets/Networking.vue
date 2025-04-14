<template>
  <v-card class="d-flex align-center justify-center" height="40" min-width="180">
    <v-card-title class="d-flex align-center pa-0 fill-width">
      <!-- eslint-disable vue/no-v-html -->
      <div class="left-content ml-2">
        <i class="pi-icon" v-html="image" />
        <span class="vertical-text">{{ interface }}</span>
      </div>
      <v-spacer />
      <div class="d-flex flex-column stacked-text mr-2">
        <div class="d-flex align-center text-caption bandwidth-row" style="margin-bottom: -8px">
          <div class="icon-label-group">
            <i class="arrow-icon-rx" v-html="arrowLeft" />
          </div>
          {{ formatBandwidth(download) }}
        </div>
        <div class="d-flex align-center text-caption bandwidth-row">
          <div class="icon-label-group">
            <i class="arrow-icon-tx" v-html="arrowRight" />
          </div>
          {{ formatBandwidth(upload) }}
        </div>
      </div>
    </v-card-title>
  </v-card>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import system_information from '@/store/system-information'
import { formatBandwidth } from '@/utils/networking'

export default Vue.extend({
  name: 'ETh0Widget',
  props: {
    interface: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      timer: 0,
      image: '',
      arrowLeft: '',
      arrowRight: '',
    }
  },
  computed: {
    upload(): number {
      const data = system_information.system?.network?.find((iface) => iface.name === this.interface)
      return data?.upload_speed ?? 0
    },
    download(): number {
      const data = system_information.system?.network?.find((iface) => iface.name === this.interface)
      return data?.download_speed ?? 0
    },
  },
  async mounted() {
    this.loadImages()
  },
  beforeDestroy() {
    clearInterval(this.timer)
  },
  methods: {
    formatBandwidth(bytesPerSecond: number): string {
      return formatBandwidth(bytesPerSecond)
    },
    async loadImages() {
      this.loadImage()
      this.loadArrowLeft()
      this.loadArrowRight()
    },
    async loadImage() {
      const url = (await import('@/assets/img/icons/pi.svg')).default as string
      const response = await axios.get(url)
      this.image = response.data
    },
    async loadArrowLeft() {
      const url = (await import('@/assets/img/icons/RX.svg')).default as string
      const response = await axios.get(url)
      this.arrowLeft = response.data
    },
    async loadArrowRight() {
      const url = (await import('@/assets/img/icons/TX.svg')).default as string
      const response = await axios.get(url)
      this.arrowRight = response.data
    },
  },
})
</script>

<style scoped>
.fill-width {
  width: 100%;
}

.left-content {
  display: flex;
  align-items: center;
}

.vertical-text {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  transform: rotate(180deg);
  font-size: 0.8rem;
  width: 20px;
  margin-left: -8px;
  margin-right: 6px;
  max-height: 40px;
  overflow: hidden;
  text-overflow: clip ;
  white-space: nowrap;
}

.pi-icon :deep(svg) {
  width: 35px;
  height: 40px;
  margin-bottom: -10px;
}

.stacked-text {
  text-align: right;
}

.bandwidth-row {
  min-width: 110px;
}

.icon-label-group {
  display: flex;
  align-items: center;
  width: 45px;
}

.bandwidth-label {
  font-size: 0.7rem;
  margin-left: 2px;
  opacity: 0.7;
}

.arrow-icon-tx :deep(svg){
  width: 50px;
  height: 16px;
  margin-top: 2px;
  margin-left: -5px;
}

.arrow-icon-rx :deep(svg){
  width: 50px;
  height: 16px;
  margin-top: 5px;
  margin-left: -6px;
}
</style>
