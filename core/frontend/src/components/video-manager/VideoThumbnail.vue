<template>
  <v-container class="d-flex flex-column align-center justify-space-between">
    <v-avatar
      :height="height"
      :width="width"
      tile
    >
      <span
        v-if="not_available"
        :style="{ border: '2px dashed' }"
        class="text-caption"
        style="opacity: 30%; padding: 20px"
      >
        Preview not<br>
        available<br>
        Add a stream<br>
        to have one
      </span>
      <spinning-logo
        v-else-if="fetching"
        size="10%"
        subtitle="Fetching thumbnail..."
      />
      <img
        v-else
        :src="thumbnail?.source"
      >
    </v-avatar>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'
import { VAvatar, VContainer } from 'vuetify/lib'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import type { Thumbnail } from '@/store/video'
import video from '@/store/video'

export default Vue.extend({
  name: 'VideoThumbnail',
  components: {
    VAvatar,
    VContainer,
    SpinningLogo,
  },
  props: {
    source: {
      type: String,
      required: true,
    },
    height: {
      type: String,
      default: 'auto',
    },
    width: {
      type: String,
      default: '280',
    },
    register: Boolean,
  },
  data() {
    return {
      thumbnail: undefined as undefined | Thumbnail,
      interval: undefined as undefined | number,
    }
  },
  computed: {
    not_available(): boolean {
      return this.register === false
    },
    fetching(): boolean {
      return this.thumbnail === undefined
    },
  },
  watch: {
    register(newValue, oldValue) {
      if (!newValue && oldValue) {
        video.stopGetThumbnailForDevice(this.source)
        if (this.interval !== undefined) {
          clearInterval(this.interval)
          this.interval = undefined
        }
      } else if (newValue && !oldValue) {
        video.startGetThumbnailForDevice(this.source)
        if (this.interval === undefined) {
          this.updateThumbnail()
          this.interval = setInterval(() => {
            this.updateThumbnail()
          }, 1000)
        }
      }
    },
  },
  mounted() {
    if (this.register) {
      video.startGetThumbnailForDevice(this.source)
    }
    this.updateThumbnail()
    this.interval = setInterval(() => {
      this.updateThumbnail()
    }, 1000)
  },
  beforeDestroy() {
    video.stopGetThumbnailForDevice(this.source)
    if (this.interval !== undefined) {
      clearInterval(this.interval)
      this.interval = undefined
    }
  },
  methods: {
    updateThumbnail() {
      const result = video.thumbnails.get(this.source)
      if (result?.status === 200) {
        this.thumbnail = result
      }
    },
  },
})
</script>
