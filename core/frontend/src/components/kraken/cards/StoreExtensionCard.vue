<template>
  <v-card
    :style="card_dominant_color ? { borderColor: card_dominant_color } : {}"
    outlined
    width="300"
    height="auto"
    elevation="2"
    class="store-extension-card"
  >
    <div
      :style="card_dominant_color ? { backgroundColor: card_dominant_color } : {}"
      class="pt-1 mb-2 pl-2 pr-3 architectures-list"
    >
      {{ compatible_architectures }}
    </div>

    <div class="content-wrapper">
      <v-img
        ref="extension_logo"
        contain
        :src="extension.extension_logo"
        height="150px"
        class="mx-3 my-2"
        @load="setDominantColor"
      />

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
    <v-card-actions class="px-3 py-2 d-flex justify-space-between align-center">
      <v-avatar size="32">
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
      <v-btn small color="primary">GET</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import ColorThief from 'color-thief'
import Vue, { PropType } from 'vue'

import { ExtensionData, Version } from '@/types/kraken'

export default Vue.extend({
  name: 'StoreExtensionCard',
  props: {
    extension: {
      type: Object as PropType<ExtensionData>,
      required: true,
    },
  },
  data() {
    return {
      card_dominant_color: undefined as string | undefined,
    }
  },
  computed: {
    is_compatible(): boolean {
      return this.extension.is_compatible ?? true
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
    extension_company(): string {
      return this.latestVersion()?.company?.name ?? 'Unknown'
    },
    extension_author(): string {
      const authors = this.latestVersion()?.authors ?? []

      if (authors.length === 0) {
        return 'Unknown'
      }

      const names = authors.slice(0, 2).map((author) => author.name).join(', ')

      return authors.length > 2 ? `${names} ...` : names
    },
  },
  methods: {
    setDominantColor() {
      console.log('Setting dominant color...')
      // @ts-expect-error - extension_logo is not an HTMLImageElement
      const img = this.$refs.extension_logo?.image as HTMLImageElement
      img.crossOrigin = 'Anonymous'

      img.onload = () => {
        const colorThief = new ColorThief()
        try {
          const color = colorThief.getColor(img)
          this.card_dominant_color = `rgb(${color.join(',')})`
        } catch (error) {
          console.error('Unable to extract logo dominant color.', error)
        }
      }
    },
    latestVersion(): Version | undefined {
      return Object.values(this.extension.versions)?.[0] ?? undefined
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
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  justify-content: space-between;
  cursor: pointer;
}

.store-extension-card:hover {
  transform: translateY(-5px);
}

.architectures-list {
  background-color: #4a90e2;
  width: fit-content;
  height: 2.4em;
  color: white;
  font-size: 12px;
  box-shadow: 0px 0px 10px 0px rgba(0, 0, 0, 0.2);
  border-radius: 0px 0px 10px 0px !important;
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
}

.extension-company {
  font-weight: bold;
  font-size: 14px;
}

.extension-authors {
  color: gray;
  font-size: 12px;
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
  opacity: 0.5;
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
