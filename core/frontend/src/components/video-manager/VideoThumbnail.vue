<template>
  <v-container class="d-flex flex-column align-center justify-space-between">
    <v-avatar
      :height="height"
      :width="width"
      tile
    >
      <span
        v-if="not_available"
        class="text-caption"
        style="border: 2px dashed; opacity: 30%; padding: 20px;"
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
import { OneMoreTime } from '@/one-more-time'
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
      update_task: new OneMoreTime({ delay: 1000, disposeWith: this, autostart: true }),
    }
  },
  computed: {
    not_available(): boolean {
      return this.register === false
    },
    fetching(): boolean {
      return this.register && this.thumbnail === undefined
    },
  },
  watch: {
    register(newValue, oldValue) {
      if (!newValue && oldValue) {
        video.stopGetThumbnailForDevice(this.source)
      } else if (newValue && !oldValue) {
        video.startGetThumbnailForDevice(this.source)
      }
    },
  },
  mounted() {
    if (this.register) {
      video.startGetThumbnailForDevice(this.source)
    }
    this.update_task.setAction(this.updateThumbnail)
  },
  beforeDestroy() {
    video.stopGetThumbnailForDevice(this.source)
  },
  methods: {
    async updateThumbnail() {
      const result = video.thumbnails.get(this.source)
      if (result?.status === 200 && result?.source !== undefined) {
        // Only accepts if the source blob URL is still valid
        const img = new Image()
        img.src = result.source
        img.onload = () => {
          this.thumbnail = result
        }
      }
    },
  },
})
</script>
