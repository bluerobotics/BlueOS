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
    <v-card class="pa-5">
      <div class="store-tab">
        <div class="grid-container">
          <StoreExtensionCard
            v-for="extension in filteredManifest"
            :key="extension.identifier + extension.name"
            :extension="extension"
          />
        </div>
      </div>
      <v-container
        v-if="manifest.length === 0"
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

import StoreExtensionCard from '@/components/kraken/cards/StoreExtensionCard.vue'
import { ExtensionData, Version } from '@/types/kraken'

export default Vue.extend({
  name: 'BackAlleyTab',
  components: {
    StoreExtensionCard,
  },
  props: {
    manifest: {
      type: Array as PropType<ExtensionData[]>,
      required: true,
    },
  },
  data() {
    return {
      query: '',
      selected_companies: [] as string[],
      selected_types: [] as string[],
      manifest_fuse: null as null | Fuse<ExtensionData>,
    }
  },
  computed: {
    extension_companies(): string[] {
      const authors = this.manifest
        .map((extension) => this.newestVersion(extension.versions)?.company?.name ?? 'unknown').sort() as string[]
      return [...new Set(authors)]
    },
    extension_types(): string[] {
      const authors = this.manifest
        .map((extension) => this.newestVersion(extension.versions)?.type ?? 'unknown')
        .sort() as string[]
      return [...new Set(authors)]
    },
    filteredManifest(): ExtensionData[] {
      // Remove not compatible in case user is not searching by search bar directly
      let data = (this.query ?? '') !== ''
        ? this.manifest_fuse?.search(this.query).map((result) => result.item) ?? []
        : this.manifest.filter((ext) => ext.is_compatible)

      // By default we remove examples if nothing is selected
      if (this.selected_companies.isEmpty() && this.selected_types.isEmpty()) {
        return data.filter((extension) => this.newestVersion(extension.versions)?.type !== 'example')
      }

      if (!this.selected_companies.isEmpty()) {
        data = data.filter((extension) => this.newestVersion(extension.versions)?.company?.name !== undefined)
          .filter((extension) => this.selected_companies
            .includes(this.newestVersion(extension.versions)?.company?.name ?? ''))
      }

      if (this.selected_types.isEmpty()) {
        return data
      }

      return data
        .filter((extension) => this.newestVersion(extension.versions)?.type !== undefined)
        .filter((extension) => this.selected_types
          .includes(this.newestVersion(extension.versions)?.type ?? ''))
    },
  },
  watch: {
    manifest: {
      handler() {
        this.manifest_fuse = new Fuse(this.manifest, {
          keys: ['identifier', 'name', 'description'],
          threshold: 0.4,
        })
      },
      immediate: true,
    },
  },
  methods: {
    newestVersion(versions: Record<string, Version>): Version | undefined {
      return Object.values(versions)?.[0] as Version | undefined
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
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.toolbar-extension {
  display: flex;
  justify-content: center;
  align-items: start;
  width: 100%;
  margin-top: 10px;
}
</style>
