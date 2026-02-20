<template>
  <v-card
    :style="card_dominant_color ? { borderColor: card_dominant_color } : {}"
    outlined
    width="400"
    height="355px"
    elevation="2"
    :class="{ 'disabled-card': !is_compatible }"
    class="store-extension-card"
  >
    <div
      v-if="is_beta_only_extension"
      class="beta-holder-container"
    >
      <v-chip
        color="red"
        small
        label
        text-color="white"
        class="beta-chip"
      >
        <div style="width: 20px;" />
        Beta
        <div style="width: 20px;" />
      </v-chip>
    </div>

    <div
      :style="img_background_style"
      class="img-background"
    />

    <div
      :style="architecture_list_style"
      class="pt-1 mb-2 pl-2 pr-3 architectures-list"
    >
      {{ compatible_architectures }}
    </div>

    <v-tooltip bottom :disabled="is_compatible">
      <template #activator="{ on, attrs }">
        <div
          class="content-wrapper"
          v-bind="attrs"
          v-on="on"
          @click="$emit('selected')"
          @keydown.left="() => {}"
        >
          <v-img
            v-once
            ref="extension_logo"
            contain
            :src="extension.extension_logo"
            height="150px"
            class="mt-3 mb-5 my-2 logo-img"
            @load="setDominantColor"
          />

          <v-card-subtitle class="px-3 py-2 ext-subtitles">
            <div
              class="line-constrained extension-name"
            >
              {{ extension.name.toUpperCase() }}
            </div>
            <div class="line-constrained extension-description">
              {{ extension.description }}
            </div>
          </v-card-subtitle>

          <div class="spacer" />
          <v-divider style="z-index: 4 !important;" />
        </div>
      </template>
      <span>This extension is not compatible with current machine architecture running BlueOS.</span>
    </v-tooltip>
    <div class="bottom-gradient-fade" />
    <div class="bottom-gradient" />
    <v-card-actions class="px-3 py-2 d-flex justify-space-between align-center card-actions">
      <v-avatar size="32" rounded="0">
        <v-img
          contain
          :src="extension.company_logo"
        />
      </v-avatar>
      <div class="extension-creators">
        <div class="line-constrained extension-company">
          {{ extension_company }}
        </div>
        <div class="extension-authors">
          {{ extension_author }}
        </div>
      </div>

      <v-tooltip bottom :disabled="!has_update_available">
        <template #activator="{ on, attrs }">
          <v-btn
            small
            class="ml-1"
            :color="is_installed ? 'success' : 'primary'"
            v-bind="attrs"
            v-on="on"
            @click="performActionClick"
          >
            {{ action_button_text }}
          </v-btn>
        </template>
        <span>Update to <strong style="white-space: nowrap;">{{ update_available_tag }}</strong></span>
      </v-tooltip>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import ColorThief from 'colorthief'
import Vue, { PropType } from 'vue'

import { getLatestVersion, isStable, updateAvailableTag } from '@/components/kraken/Utils'
import { ExtensionData, InstalledExtensionData } from '@/types/kraken'

export interface ImgProcessedResult {
  url: string
  color: string
  isLight: boolean
  isTransparent: boolean
}

export default Vue.extend({
  name: 'StoreExtensionCard',
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
    installed: {
      type: Array as PropType<InstalledExtensionData[]>,
      required: true,
    },
    imgsProcessed: {
      type: Object as PropType<Record<string, ImgProcessedResult>>,
      required: true,
    },
  },
  data() {
    return {
      card_dominant_color: undefined as string | undefined,
      is_card_mostly_transparent: false,
      is_card_dominant_color_light: false,
    }
  },
  computed: {
    installed_extension(): InstalledExtensionData | undefined {
      return this.installed.find((installed) => installed.identifier === this.extension.identifier)
    },
    is_compatible(): boolean {
      return this.extension.is_compatible ?? true
    },
    is_installed(): boolean {
      return this.installed_extension !== undefined
    },
    update_available_tag(): undefined | string {
      if (this.is_installed && this.installed_extension?.tag) {
        return updateAvailableTag(
          this.extension.versions,
          this.installed_extension.tag,
          !isStable(this.installed_extension.tag),
        )
      }

      return undefined
    },
    has_update_available(): boolean {
      return this.update_available_tag !== undefined
    },
    compatible_architectures(): string {
      const archs = [
        ...new Set(
          Object.values(this.extension.versions)
            .flatMap((version) => version.images)
            .flatMap((image) => image.platform.architecture),
        ),
      ]
      archs.sort()
      return archs.join(', ')
    },
    action_button_text(): string {
      if (!this.is_installed) {
        return 'GET'
      }

      return this.has_update_available ? 'UPDATE' : 'INSTALLED'
    },
    architecture_list_style(): Record<string, string> {
      if (this.card_dominant_color === undefined) {
        return {
          color: this.$vuetify.theme.dark ? 'white' : 'black',
        }
      }

      return {
        color: this.is_card_dominant_color_light ? 'black' : 'white',
        backgroundColor: this.card_dominant_color,
      }
    },
    extension_company(): string {
      return getLatestVersion(this.extension.versions)?.company?.name ?? 'Unknown'
    },
    extension_author(): string {
      const authors = getLatestVersion(this.extension.versions)?.authors ?? []

      if (authors.length === 0) {
        return 'Unknown'
      }

      const names = authors.map((author) => author.name).join(', ')

      return authors.length > 2 ? `${names} ...` : names
    },
    img_background_style(): Record<string, string> {
      if (this.card_dominant_color) {
        if (this.is_card_mostly_transparent) {
          return {
            backgroundColor: this.is_card_dominant_color_light ? '#111' : '#EEE',
          }
        }

        return {
          backgroundColor: this.card_dominant_color,
        }
      }

      return {}
    },
    is_beta_only_extension(): boolean {
      return Object.values(this.extension.versions).every((version) => !isStable(version.tag))
    },
  },
  methods: {
    async setDominantColor() {
      if (this.extension.extension_logo && this.imgsProcessed[this.extension.extension_logo]) {
        const { color, isLight, isTransparent } = this.imgsProcessed[this.extension.extension_logo]
        this.card_dominant_color = color
        this.is_card_dominant_color_light = isLight
        this.is_card_mostly_transparent = isTransparent
        return
      }

      // @ts-expect-error - extension_logo is not an HTMLImageElement
      const img = this.$refs.extension_logo?.image as HTMLImageElement
      img.crossOrigin = 'Anonymous'

      img.onload = () => {
        const colorThief = new ColorThief()
        try {
          const color = colorThief.getColor(img)

          this.card_dominant_color = `rgb(${color.join(',')})`
          this.is_card_dominant_color_light = this.getLuminance(color[0], color[1], color[2]) > 128
          this.is_card_mostly_transparent = this.isImgTransparent(img)

          this.$emit('img-processed', {
            url: this.extension.extension_logo,
            color: this.card_dominant_color,
            isLight: this.is_card_dominant_color_light,
            isTransparent: this.is_card_mostly_transparent,
          })
        } catch (error) {
          console.error('Unable to extract logo dominant color.', error)
        }
      }
    },
    isImgTransparent(img: HTMLImageElement): boolean {
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      canvas.width = img.naturalWidth
      canvas.height = img.naturalHeight
      context?.drawImage(img, 0, 0, canvas.width, canvas.height)

      const data = context?.getImageData(0, 0, img.width, img.height)?.data

      if (!data) {
        return false
      }

      let transparentPixelCount = 0
      for (let i = 0; i < data.length; i += 10) {
        const alpha = data[i + 3]
        if (alpha === 0) {
          transparentPixelCount += 1
        }
      }

      // If more than 20% of the image is transparent, render against dominant color
      if (transparentPixelCount / (data.length / 4) > 0.2) {
        return true
      }

      return false
    },
    getLuminance(r: number, g: number, b: number): number {
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

      return lum
    },
    performActionClick() {
      if (this.has_update_available) {
        const payload: InstalledExtensionData = {
          identifier: this.extension.identifier,
          name: this.extension.name,
          docker: this.extension.docker,
          tag: this.update_available_tag ?? '',
          enabled: true,
          permissions: '',
          user_permissions: '',
        }
        this.$emit('update', payload, payload.tag)
        return
      }

      this.$emit('selected')
    },
  },
})
</script>

<style scoped>
.store-extension-card {
  display: flex;
  flex-direction: column;
  border-radius: 8px;
  transition: transform 0.3s;
  box-sizing: border-box;
  -moz-box-sizing: border-box;
  -webkit-box-sizing: border-box;
  border: 0;
  position: relative;
  overflow: hidden;
}

.store-extension-card:hover {
  transform: translateY(-5px);
}

.img-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 75%;
  z-index: 0;
  border-radius: 8px !important;
}

.logo-img {
  flex-grow: 0;
  z-index: 0 !important;
}

.bottom-gradient {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 55px;
  z-index: 3 !important;
}

.bottom-gradient-fade {
  position: absolute;
  bottom: 55px;
  left: 0;
  width: 100%;
  height: 80px;
  backdrop-filter: blur(10px);
  z-index: 3 !important;
}

.theme--light .bottom-gradient {
  background-color: #FFF;
}

.theme--light .bottom-gradient-fade {
  background: linear-gradient(0deg, #FFF 60%, rgba(255, 255, 255, 0.65));
}

.theme--dark .bottom-gradient {
  background-color: var(--v-oyster-darken1);
}

.theme--dark .bottom-gradient-fade {
  background: linear-gradient(0deg, var(--v-oyster-darken1) 60%, rgba(30, 30, 30, 0.65));
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  justify-content: space-between;
  cursor: pointer;
}

.ext-subtitles {
  z-index: 4 !important;
}

.card-actions {
  z-index: 4 !important;
}

.spacer {
  flex-grow: 1;
}

.architectures-list {
  width: fit-content;
  height: 2.4em;
  color: white;
  font-size: 12px;
  box-shadow: 0 0 8px 0 rgba(0, 0, 0, 0.5);
  border-radius: 8px 0 10px 0 !important;
  z-index: 4 !important;
}

.line-constrained {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-box-orient: vertical;
}

.extension-name {
  font-weight: bold;
  font-size: 18px;
  max-height: 1.4em;
  line-clamp: 1;
  -webkit-line-clamp: 1;
}

.extension-description {
  color: gray;
  font-size: 14px;
  max-height: 3.6em;
  line-clamp: 2;
  -webkit-line-clamp: 2;
}

.extension-creators {
  flex-grow: 1;
  margin-left: 8px;
  min-width: 0; /* Ensure flexbox doesn't force a minimum width */
}

.extension-company {
  font-weight: bold;
  font-size: 14px;
  line-clamp: 1;
  -webkit-line-clamp: 1;
}

.extension-authors {
  color: gray;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: calc(100% - 10px);
}

.v-card-actions {
  margin-top: auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.v-img {
  border-radius: 8px;
}

.v-avatar img {
  object-fit: cover;
}

.disabled-card {
  opacity: 0.7;
  position: relative;
}
.disabled-card::before {
  opacity: 1;
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  background: repeating-linear-gradient(
    135deg,
    rgba(255, 255, 255, 0),
    rgba(255, 255, 255, 0) 15px,
    rgba(100, 85, 85, 0.4) 10px,
    rgba(100, 85, 85, 0.4) 16px
  );
  pointer-events: none;
}

.beta-holder-container {
  position: absolute;
  top: 20px;
  right: 20px;
  transform: translate(50%, -50%) rotateZ(45deg);
  z-index: 5 !important;
}

.beta-chip {
  transform-origin: center;
}

</style>
