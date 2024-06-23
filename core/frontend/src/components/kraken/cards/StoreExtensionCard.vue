<template>
  <v-card
    :style="card_dominant_color ? { borderColor: card_dominant_color } : {}"
    outlined
    width="400"
    height="auto"
    elevation="2"
    :class="{ 'disabled-card': !is_compatible }"
    class="store-extension-card"
  >
    <div
      :style="card_dominant_color ? { backgroundColor: card_dominant_color } : {}"
      class="img-background"
    />
    <v-img
      v-once
      ref="extension_logo"
      contain
      :src="extension.extension_logo"
      class="background-image"
      eager="true"
      @load="setDominantColor"
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
          <div class="spacer" />

          <v-card-subtitle class="px-3 py-2">
            <div
              class="extension-name"
            >
              {{ extension.name.toUpperCase() }}
            </div>
            <div class="extension-description">
              {{ extension.description }}
            </div>
          </v-card-subtitle>

          <v-divider />
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
        <div class="extension-company">
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
  },
  data() {
    return {
      card_dominant_color: undefined as string | undefined,
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

      return archs.join(', ')
    },
    action_button_text(): string {
      if (!this.is_installed) {
        return 'GET'
      }

      return this.has_update_available ? 'UPDATE' : 'INSTALLED'
    },
    architecture_list_style(): Record<string, string> {
      const style: Record<string, string> = {
        color: this.is_card_dominant_color_light ? 'black' : 'white',
      }

      if (this.card_dominant_color) {
        style.backgroundColor = this.card_dominant_color
      }

      return style
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
  },
  methods: {
    setDominantColor() {
      // @ts-expect-error - extension_logo is not an HTMLImageElement
      const img = this.$refs.extension_logo?.image as HTMLImageElement
      img.crossOrigin = 'Anonymous'

      img.onload = () => {
        const colorThief = new ColorThief()
        try {
          const color = colorThief.getColor(img)

          this.is_card_dominant_color_light = this.getLuminance(color[0], color[1], color[2]) > 128
          this.card_dominant_color = `rgb(${color.join(',')})`
        } catch (error) {
          console.error('Unable to extract logo dominant color.', error)
        }
      }
    },
    getLuminance(r: number, g: number, b: number): number {
      const lum = 0.2126 * r + 0.7152 * g + 0.0722 * b

      return lum
    },
    performActionClick() {
      if (this.has_update_available) {
        this.$emit('update', this.update_available_tag)
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
  border: 2px solid transparent;
  position: relative;
  overflow: hidden;
}

.store-extension-card:hover {
  transform: translateY(-5px);
}

.img-background {
  position: absolute;
  top: -1px;
  left: -1px;
  width: calc(100% + 2px);
  height: 90%;
  z-index: 0;
  border-radius: 0px !important;
}

.background-image {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  border-radius: 8px;
  height: auto;
  z-index: 1;
}

.spacer {
  flex-grow: 1;
  min-height: 150px;
}

.bottom-gradient {
  position: absolute;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 55px;
  background-color: var(--v-oyster-darken1);
  z-index: 3 !important;
}
.bottom-gradient-fade {
  position: absolute;
  bottom: 55px;
  left: 0;
  width: 100%;
  height: 80px;
  background: linear-gradient(0deg, var(--v-oyster-darken1), rgba(30, 30, 30, 0.6));
  backdrop-filter: blur(10px);
  z-index: 3 !important;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  justify-content: space-between;
  cursor: pointer;
  z-index: 4 !important;
}

.card-actions {
  z-index: 4 !important;
}

.architectures-list {
  width: fit-content;
  height: 2.4em;
  color: white;
  font-size: 12px;
  box-shadow: 0px 0px 10px 0px rgba(0, 0, 0, 0.2);
  border-radius: 0px 0px 10px 0px !important;
  z-index: 4 !important;
}

.extension-name {
  font-weight: bold;
  font-size: 18px;
}

.extension-description {
  color: gray;
  font-size: 14px;
}

.extension-creators {
  flex-grow: 1;
  margin-left: 8px;
  min-width: 0; /* Ensure flexbox doesn't force a minimum width */
}

.extension-company {
  font-weight: bold;
  font-size: 14px;
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
</style>
