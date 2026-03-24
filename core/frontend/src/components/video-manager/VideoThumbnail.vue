<template>
  <v-container class="d-flex flex-column align-center justify-space-between">
    <div
      class="thumbnail-frame d-flex align-center justify-center"
      :style="{ width: parsedWidth, aspectRatio: '16 / 9' }"
    >
      <span
        v-if="disabled"
        class="text-caption text-center placeholder-box"
      >
        Thumbnails disabled<br>
        for this source.
      </span>
      <span
        v-else-if="not_available"
        class="text-caption text-center placeholder-box"
      >
        Preview not available,<br>
        add a stream to have one.
      </span>
      <spinning-logo
        v-else-if="fetching"
        size="10%"
        subtitle="Fetching thumbnail..."
      />
      <span
        v-else-if="idle_placeholder"
        class="text-caption text-center placeholder-box"
      >
        Preview not requested,<br>
        use the controls to fetch one.
      </span>
      <img
        v-else
        :src="thumbnail?.source"
        style="width: 100%; height: 100%; object-fit: contain;"
      >
      <div
        v-if="is_pirate_mode && register"
        class="thumbnail-overlay text-caption"
      >
        <template v-if="continuous_mode">
          LIVE
          <template v-if="last_fetch_ms !== null">
            {{ last_fetch_ms }}ms
          </template>
        </template>
        <template v-else-if="snapshot_in_progress">
          fetching...
        </template>
        <template v-else-if="thumbnail">
          <template v-if="last_fetch_ms !== null">
            {{ last_fetch_ms }}ms
          </template>
        </template>
        <template v-else>
          idle
        </template>
      </div>
      <div
        v-if="register"
        class="thumbnail-controls d-flex align-center"
        @click.stop.prevent
      >
        <v-tooltip bottom>
          <template #activator="{ on, attrs }">
            <v-btn
              text
              dark
              class="control-btn"
              :disabled="snapshot_in_progress || snapshot_cooldown || continuous_mode"
              v-bind="attrs"
              v-on="on"
              @click="fetchSingleThumbnail"
            >
              <v-icon small>
                mdi-camera
              </v-icon>
            </v-btn>
          </template>
          <span>Fetch a single thumbnail</span>
        </v-tooltip>
        <span class="control-separator">|</span>
        <v-tooltip bottom>
          <template #activator="{ on, attrs }">
            <v-btn
              text
              dark
              class="control-btn"
              v-bind="attrs"
              v-on="on"
              @click="toggleContinuous"
            >
              <v-icon small>
                {{ continuous_mode ? 'mdi-pause' : 'mdi-play' }}
              </v-icon>
            </v-btn>
          </template>
          <span>
            {{ continuous_mode ? 'Stop continuous thumbnails' : 'Start continuous thumbnails (1s)' }}
          </span>
        </v-tooltip>
      </div>
    </div>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'
import { VContainer } from 'vuetify/lib'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import settings from '@/libs/settings'
import { OneMoreTime } from '@/one-more-time'
import type { Thumbnail } from '@/store/video'
import video from '@/store/video'

export default Vue.extend({
  name: 'VideoThumbnail',
  components: {
    VContainer,
    SpinningLogo,
  },
  props: {
    source: {
      type: String,
      required: true,
    },
    width: {
      type: String,
      default: '280',
    },
    register: Boolean,
    disabled: Boolean,
    autoplay: Boolean,
  },
  data() {
    return {
      thumbnail: undefined as undefined | Thumbnail,
      update_task: new OneMoreTime({ delay: 1000, disposeWith: this, autostart: true }),
      stopDebounceTimer: undefined as ReturnType<typeof setTimeout> | undefined,
      continuous_mode: false,
      snapshot_in_progress: false,
      snapshot_cooldown: false,
      last_fetch_ms: null as number | null,
    }
  },
  computed: {
    not_available(): boolean {
      return this.register === false
    },
    fetching(): boolean {
      return this.register && this.thumbnail === undefined
        && (this.continuous_mode || this.snapshot_in_progress)
    },
    idle_placeholder(): boolean {
      return this.register && this.thumbnail === undefined
        && !this.continuous_mode && !this.snapshot_in_progress
    },
    parsedWidth(): string {
      return /^\d+$/.test(this.width) ? `${this.width}px` : this.width
    },
    is_pirate_mode(): boolean {
      return settings.is_pirate_mode
    },
  },
  watch: {
    register(newValue, oldValue) {
      if (!newValue && oldValue) {
        clearTimeout(this.stopDebounceTimer)
        this.stopDebounceTimer = setTimeout(() => {
          if (!this.register) {
            video.stopGetThumbnailForDevice(this.source)
            this.continuous_mode = false
          }
        }, 15000)
      } else if (newValue && !oldValue) {
        clearTimeout(this.stopDebounceTimer)
        this.stopDebounceTimer = undefined
        if (this.continuous_mode) {
          video.startGetThumbnailForDevice(this.source)
        }
      }
    },
  },
  mounted() {
    this.update_task.setAction(this.updateThumbnail)
    if (this.autoplay && this.register) {
      this.continuous_mode = true
      video.startGetThumbnailForDevice(this.source)
    }
  },
  beforeDestroy() {
    clearTimeout(this.stopDebounceTimer)
    const blobUrl = video.thumbnails.get(this.source)?.source
    if (blobUrl !== undefined) {
      URL.revokeObjectURL(blobUrl)
    }
    video.stopGetThumbnailForDevice(this.source)
  },
  methods: {
    async updateThumbnail() {
      const result = video.thumbnails.get(this.source)
      if (result?.status === 200 && result?.source !== undefined && result.source !== this.thumbnail?.source) {
        const img = new Image()
        img.src = result.source
        img.onload = () => {
          this.last_fetch_ms = result.roundtripMs ?? null
          this.thumbnail = result
          if (this.snapshot_in_progress) {
            this.snapshot_in_progress = false
            this.snapshot_cooldown = true
            setTimeout(() => { this.snapshot_cooldown = false }, 1000)
            video.stopGetThumbnailForDevice(this.source)
          }
        }
      }
    },
    async fetchSingleThumbnail(): Promise<void> {
      this.snapshot_in_progress = true
      video.startGetThumbnailForDevice(this.source)
    },
    toggleContinuous(): void {
      this.continuous_mode = !this.continuous_mode
      if (this.continuous_mode) {
        video.startGetThumbnailForDevice(this.source)
      } else {
        video.stopGetThumbnailForDevice(this.source)
      }
    },
  },
})
</script>

<style scoped>
.thumbnail-frame {
  position: relative;
  overflow: hidden;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.08);
  max-height: 100%;
}

.thumbnail-overlay {
  position: absolute;
  top: 4px;
  left: 4px;
  background: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  line-height: 1.2;
  pointer-events: none;
}

.thumbnail-controls {
  position: absolute;
  bottom: 4px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.6);
  border-radius: 4px;
  padding: 0;
  overflow: hidden;
}

.control-btn {
  min-width: 40px !important;
  height: 32px !important;
  padding: 0 14px !important;
  border-radius: 0 !important;
  margin: 0 !important;
  letter-spacing: normal !important;
}

.control-separator {
  color: rgba(255, 255, 255, 0.3);
  font-size: 18px;
  line-height: 32px;
  user-select: none;
}

.placeholder-box {
  border: 2px dashed;
  opacity: 0.3;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
