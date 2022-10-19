<template>
  <v-container fluid>
    <v-dialog
      v-model="show_dialog"
      width="80%"
    >
      <pull-progress
        :progress="pull_output"
        :show="show_pull_output"
      />
      <extension-modal
        :extension="selected_extension"
        :installed="installedVersion()"
        @clicked="install"
      />
    </v-dialog>
    <v-tabs
      v-model="tab"
      fixed-tabs
    >
      <v-tab>Installed</v-tab>
      <v-tab>Store</v-tab>
    </v-tabs>
    <div
      v-if="tab === 1"
      class="d-flex pa-5"
    >
      <v-row dense>
        <v-col
          v-for="extension in manifest"
          :key="extension.website + extension.name"
          class="pa-2"
        >
          <extension-card
            :extension="extension"
            @clicked="showModal(extension)"
          />
        </v-col>
      </v-row>
      <v-container
        v-if="manifest.length === 0"
        class="text-center"
      >
        <p class="text-h6">
          No Extensions available.
        </p>
      </v-container>
    </div>
    <v-row>
      <v-col
        v-if="tab === 0"
        class="pa-5"
      >
        <v-row
          v-for="extension in installed_extensions"
          :key="extension.name"
          dense
        >
          <v-col
            class="pa-2"
          >
            <v-card>
              <v-card-title>
                {{ extension.name.replace('/', '') }}: <span style="color: grey;"> {{ extension.tag }}</span>
              </v-card-title>
              <v-card-text>
                {{ getStatus(extension) }}
              </v-card-text>
              <v-card-text>
                Permissions:
                <pre> {{ extension.permissions }} </pre>
              </v-card-text>
              <v-card-actions>
                <v-btn @click="uninstall(extension)">
                  Uninstall
                </v-btn>
              </v-card-actions>
            </v-card>
          </v-col>
        </v-row>
        <v-container
          v-if="installed_extensions.length === 0"
          class="text-center"
        >
          <p
            v-if="dockers_fetch_done"
            class="text-h6"
          >
            No Extensions installed.
          </p>
          <p
            v-else
            class="text-h6"
          >
            Fetching Extensions
          </p>
        </v-container>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import ExtensionCard from '@/components/kraken/ExtensionCard.vue'
import ExtensionModal from '@/components/kraken/ExtensionModal.vue'
import PullProgress from '@/components/utils/PullProgress.vue'
import Notifier from '@/libs/notifier'
import { kraken_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import PullTracker from '@/utils/pull_tracker'

import { ExtensionData, InstalledExtensionData, RunningContainer } from '../types/kraken'

const API_URL = '/kraken/v1.0'

const notifier = new Notifier(kraken_service)

export default Vue.extend({
  name: 'ExtensionManagerView',
  components: {
    ExtensionCard,
    ExtensionModal,
    PullProgress,
  },
  data() {
    return {
      tab: 0,
      show_dialog: false,
      installed_extensions: [] as InstalledExtensionData[],
      selected_extension: null as (null | ExtensionData),
      running_containers: [] as RunningContainer[],
      manifest: [] as ExtensionData[],
      dockers_fetch_done: false,
      show_pull_output: false,
      pull_output: '',
    }
  },
  mounted() {
    this.fetchManifest()
    this.fetchInstalledExtensions()
    this.fetchRunningContainers()
  },
  methods: {
    getStatus(extension: InstalledExtensionData): string {
      return this.running_containers.filter(
        (container) => container.image === `${extension.name}:${extension.tag}`,
      )
        .first()?.status ?? 'N/A'
    },
    async fetchManifest(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/extensions_manifest`,
        timeout: 3000,
      })
        .then((response) => {
          this.manifest = response.data
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_MANIFEST_FETCH_FAIL', error)
        })
    },
    async fetchInstalledExtensions(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/installed_extensions`,
        timeout: 30000,
      })
        .then((response) => {
          this.installed_extensions = response.data
          this.dockers_fetch_done = true
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_INSTALLED_FETCH_FAIL', error)
        })
    },
    showModal(extension: ExtensionData) {
      this.show_dialog = true
      this.selected_extension = extension
    },
    async install(tag: string) {
      this.show_dialog = false
      this.show_pull_output = true
      const tracker = new PullTracker(() => {
        setTimeout(() => {
          this.show_pull_output = false
        }, 1000)
      })

      await back_axios({
        url: `${API_URL}/extension/install`,
        method: 'POST',
        data: {
          identifier: this.selected_extension?.identifier,
          name: this.selected_extension?.docker,
          tag,
          enabled: true,
          permissions: JSON.stringify(this.selected_extension?.versions[tag].permissions),
        },
        onDownloadProgress: (progressEvent) => {
          tracker.digestNewData(progressEvent)
          this.pull_output = tracker.pull_output
        },
      })
        .then(() => {
          this.show_dialog = false
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        })
    },
    async uninstall(extension: ExtensionData) {
      await axios.post(`${API_URL}/extension/uninstall`, null, {
        params: {
          extension_name: extension.name,
        },
      })
        .then(() => {
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_UNINSTALL_FAIL', error)
        })
    },
    installedVersion(): string | undefined {
      const extension_name = this.selected_extension?.docker
      if (!extension_name) {
        return undefined
      }
      return this.installed_extensions.find((extension) => extension.name === extension_name)?.tag
    },
    async fetchRunningContainers(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/list_containers`,
        timeout: 30000,
      })
        .then((response) => {
          this.running_containers = response.data
        })
        .catch((error) => {
          notifier.pushBackError('RUNNING_CONTAINERS_FETCH_FAIL', error)
        })
    },
  },
})
</script>

<style>
  div.readme h1 {
    margin: 5px;
  }
</style>
