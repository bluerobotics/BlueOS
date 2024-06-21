<template>
  <v-container fluid>
    <!-- Progress Pull -->
    <!-- Extension Detail Modal -->
    <!-- Log Modal -->
    <ExtensionSettingsModal
      v-model="show_settings"
      @refresh="fetchManifest"
    />
    <v-toolbar>
      <v-spacer />
      <v-tabs
        v-model="tab"
        fixed-tabs
      >
        <v-tab class="tab-text">
          <v-icon class="mr-3">
            mdi-incognito
          </v-icon>
          Back Alley
        </v-tab>
        <v-tab class="tab-text">
          <v-icon class="mr-3">
            mdi-package-variant
          </v-icon>
          Bazaar
        </v-tab>
        <v-tab class="tab-text">
          <v-icon class="mr-3">
            mdi-bookshelf
          </v-icon>
          Installed
        </v-tab>
      </v-tabs>
      <v-spacer />
      <v-btn
        v-tooltip="'Settings'"
        icon
        hide-details="auto"
        @click="show_settings = true"
      >
        <v-icon>mdi-cog</v-icon>
      </v-btn>
    </v-toolbar>
    <v-card v-if="manifest_fetching || has_manifest_error" class="pa-5">
      <v-container
        class="text-center fill-height d-flex flex-column justify-center align-center mt-5"
      >
        <SpinningLogo
          v-if="!has_manifest_error"
          size="100"
          subtitle="Fetching extension Manifest"
        />
        <div v-else>
          <v-icon
            class="mt-16 mb-5"
            color="red"
            size="100"
          >
            mdi-alert-octagon
          </v-icon>
          <v-card-title class="mb-5">
            Failed to fetch extension manifest.
          </v-card-title>
        </div>
      </v-container>
    </v-card>
    <BackAlleyTab
      v-else-if="is_back_alley_tab"
      :manifest="manifest"
    />
    <BazaarTab v-else-if="is_bazaar_tab" />
    <InstalledExtensionsTab v-else-if="is_installed_tab" />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import BackAlleyTab from '@/components/kraken/BackAlleyTab.vue'
import BazaarTab from '@/components/kraken/BazaarTab.vue'
import InstalledExtensionsTab from '@/components/kraken/InstalledExtensionsTab.vue'
import KrakenAPI from '@/components/kraken/KrakenManager'
import ExtensionSettingsModal from '@/components/kraken/modals/ExtensionSettingsModal.vue'

import { ExtensionData } from '../types/kraken'

export default Vue.extend({
  name: 'ExtensionManagerView',
  components: {
    BackAlleyTab,
    BazaarTab,
    InstalledExtensionsTab,
    ExtensionSettingsModal,
    SpinningLogo,
  },
  data() {
    return {
      tab: 0,
      show_settings: false,
      manifest_fetching: true,
      manifest_error: '' as string | undefined,
      manifest: [] as ExtensionData[],
    }
  },
  computed: {
    is_back_alley_tab(): boolean {
      return this.tab === 0
    },
    is_bazaar_tab(): boolean {
      return this.tab === 1
    },
    is_installed_tab(): boolean {
      return this.tab === 2
    },
    has_manifest_error(): boolean {
      return this.manifest_error !== undefined
    },
  },
  mounted() {
    this.fetchManifest()
  },
  methods: {
    async fetchManifest(): Promise<void> {
      this.manifest_error = undefined
      this.manifest_fetching = true

      try {
        const response = await KrakenAPI.fetchConsolidatedManifests()

        this.manifest = response.map((extension: ExtensionData) => ({
          ...extension,
          is_compatible: this.checkExtensionCompatibility(extension),
        }))
      } catch (error) {
        this.manifest_error = String(error)
      } finally {
        this.manifest_fetching = false
      }
    },
    checkExtensionCompatibility(extension: ExtensionData): boolean {
      return Object.values(extension.versions).some(
        (version) => version.images.some(
          (image) => image.compatible,
        ),
      )
    },
  },
})
</script>

<style scoped>
.tab-text {
  white-space: nowrap !important;
}
</style>
