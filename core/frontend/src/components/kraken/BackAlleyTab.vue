<template>
  <div>
    <v-toolbar height="0" extension-height="70" elevation="0">
      <template #extension>
        <div class="toolbar-extension">
          <v-text-field
            v-model="query"
            solo
            dense
            filled
            clearable
            class="query-text-field"
            placeholder="Search Extensions"
            prepend-inner-icon="mdi-magnify"
          />
          <v-menu
            transition="fade-transition"
            offset-y
            nudge-left="110"
            nudge-bottom="10"
            :close-on-content-click="false"
          >
            <template #activator="{ on, attrs }">
              <v-btn
                class="mx-6"
                height="41"
                rounded
                elevation="3"
                color="secondary"
                v-bind="attrs"
                v-on="on"
              >
                Providers
                <v-icon right>
                  mdi-chevron-down
                </v-icon>
              </v-btn>
            </template>

            <v-card elevation="1" width="250">
              <v-btn
                class="my-4 ml-6"
                width="200"
                rounded
                @click="selected_companies = []"
              >
                Clear
                <v-icon right>
                  mdi-trash-can
                </v-icon>
              </v-btn>
              <v-divider />
              <v-virtual-scroll
                :item-height="40"
                :items="extension_companies"
                class="my-3"
                height="400px"
              >
                <template #default="{ item }">
                  <v-card-text>
                    <v-checkbox
                      v-model="selected_companies"
                      :label="item"
                      :value="item"
                      class="pa-0 pl-3 ma-0"
                    />
                  </v-card-text>
                </template>
              </v-virtual-scroll>
              <v-divider />
            </v-card>
          </v-menu>
          <v-menu
            transition="fade-transition"
            offset-y
            nudge-left="149"
            nudge-bottom="10"
            :close-on-content-click="false"
          >
            <template #activator="{ on, attrs }">
              <v-btn
                class="mr-6"
                height="41"
                rounded
                elevation="3"
                color="secondary"
                v-bind="attrs"
                v-on="on"
              >
                Types
                <v-icon right>
                  mdi-chevron-down
                </v-icon>
              </v-btn>
            </template>

            <v-card elevation="1" width="250">
              <v-btn
                class="my-4 ml-6"
                width="200"
                rounded
                @click="selected_types = []"
              >
                Clear
                <v-icon right>
                  mdi-trash-can
                </v-icon>
              </v-btn>
              <v-divider />
              <v-virtual-scroll
                :item-height="40"
                :items="extension_types"
                class="my-3"
                height="400px"
              >
                <template #default="{ item }">
                  <v-card-text>
                    <v-checkbox
                      v-model="selected_types"
                      :label="item"
                      :value="item"
                      class="pa-0 pl-3 ma-0"
                    />
                  </v-card-text>
                </template>
              </v-virtual-scroll>
              <v-divider />
            </v-card>
          </v-menu>
        </div>
      </template>
    </v-toolbar>
    <v-card v-if="show_info_card" class="pa-5">
      <v-container
        class="text-center fill-height d-flex flex-column justify-center align-center mt-5"
      >
        <SpinningLogo
          v-if="manifest_is_loading"
          size="200"
          subtitle="Fetching extension Manifest"
        />
        <div v-else>
          <v-icon
            class="mt-16 mb-5"
            color="red"
            size="100"
          >
            {{ internet_offline ? 'mdi-ethernet-cable-off' : 'mdi-alert-octagon' }}
          </v-icon>
          <v-card-title class="mb-5">
            {{ internet_offline ? 'Backend is not connected to the internet.' : 'Failed to fetch extension manifest.' }}
          </v-card-title>
        </div>
      </v-container>
    </v-card>
    <v-card v-else class="pa-5">
      <div class="store-tab">
        <div class="grid-container">
          <StoreExtensionCard
            v-for="extension in filtered_manifest"
            :key="extension.identifier + extension.name"
            :extension="extension"
            :installed="installed_extensions"
            :imgs-processed="imgs_processed"
            @selected="$emit('clicked', extension)"
            @update="update"
            @img-processed="addImgProcessed"
          />
        </div>
      </div>
      <v-container
        v-if="filtered_manifest.length === 0"
        class="d-flex flex-column justify-center align-center mt-5"
      >
        <v-card-title class="mb-5">
          No Extensions Available
        </v-card-title>
      </v-container>
    </v-card>
  </div>
</template>

<script lang="ts">
import Fuse from 'fuse.js'
import Vue, { PropType } from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import StoreExtensionCard, { ImgProcessedResult } from '@/components/kraken/cards/StoreExtensionCard.vue'
import { getLatestVersion } from '@/components/kraken/Utils'
import helper from '@/store/helper'
import { ExtensionData, InstalledExtensionData } from '@/types/kraken'

export default Vue.extend({
  name: 'BackAlleyTab',
  components: {
    StoreExtensionCard,
    SpinningLogo,
  },
  props: {
    manifest: {
      type: [String, Array] as PropType<undefined | string | ExtensionData[]>,
      required: false,
      default: undefined,
    },
    installedExtensions: {
      type: Object as PropType<undefined | Record<string, InstalledExtensionData>>,
      required: false,
      default: undefined,
    },
  },
  data() {
    return {
      query: '',
      selected_companies: [] as string[],
      selected_types: [] as string[],
      manifest_fuse: undefined as undefined | Fuse<ExtensionData>,
      imgs_processed: {} as Record<string, ImgProcessedResult>,
    }
  },
  computed: {
    installed_extensions(): InstalledExtensionData[] {
      return Object.values(this.installedExtensions ?? {})
    },
    manifest_is_loading(): boolean {
      return this.manifest === undefined
    },
    manifest_has_error(): boolean {
      return typeof this.manifest === 'string'
    },
    is_manifest_invalid(): boolean {
      return this.manifest_is_loading || this.manifest_has_error
    },
    internet_offline(): boolean {
      return !helper.has_internet
    },
    show_info_card(): boolean {
      return this.is_manifest_invalid || this.internet_offline
    },
    manifest_data(): ExtensionData[] {
      if (this.is_manifest_invalid) {
        return []
      }

      return (this.manifest as ExtensionData[]).sort(
        (a, b) => (b?.repo_info?.downloads ?? 0) - (a?.repo_info?.downloads ?? 0),
      )
    },
    extension_companies(): string[] {
      const authors = this.manifest_data
        .map((extension) => getLatestVersion(extension.versions)?.company?.name ?? 'unknown').sort() as string[]
      return [...new Set(authors)]
    },
    extension_types(): string[] {
      const authors = this.manifest_data
        .map((extension) => getLatestVersion(extension.versions)?.type ?? 'unknown')
        .sort() as string[]
      return [...new Set(authors)]
    },
    filtered_manifest(): ExtensionData[] {
      // Remove not compatible in case user is not searching by search bar directly
      let data = (this.query ?? '') !== ''
        ? this.manifest_fuse?.search(this.query).map((result) => result.item) ?? []
        : this.manifest_data.filter((ext) => ext.is_compatible)

      // By default we remove examples if nothing is selected
      if (this.selected_companies.isEmpty() && this.selected_types.isEmpty()) {
        return data.filter((extension) => getLatestVersion(extension.versions)?.type !== 'example')
      }

      if (!this.selected_companies.isEmpty()) {
        data = data.filter((extension) => getLatestVersion(extension.versions)?.company?.name !== undefined)
          .filter((extension) => this.selected_companies
            .includes(getLatestVersion(extension.versions)?.company?.name ?? ''))
      }

      if (this.selected_types.isEmpty()) {
        return data
      }

      return data
        .filter((extension) => getLatestVersion(extension.versions)?.type !== undefined)
        .filter((extension) => this.selected_types
          .includes(getLatestVersion(extension.versions)?.type ?? ''))
    },
  },
  watch: {
    manifest: {
      handler() {
        this.manifest_fuse = new Fuse(this.manifest_data, {
          keys: ['identifier', 'name', 'description'],
          threshold: 0.4,
        })
      },
      immediate: true,
    },
  },
  methods: {
    addImgProcessed(res: ImgProcessedResult) {
      this.$set(this.imgs_processed, res.url, res)
    },
    update(ext: InstalledExtensionData, tag: string) {
      this.$emit('update', ext, tag)
    },
  },
})
</script>

<style scoped>
.query-text-field {
  max-width: 620px;
}

.store-tab {
  padding: 16px;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
  justify-content: center;
}

.toolbar-extension {
  display: flex;
  justify-content: center;
  align-items: start;
  width: 100%;
  margin-top: 10px;
}

@media (max-width: 677px) {
  .grid-container {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
}
</style>
