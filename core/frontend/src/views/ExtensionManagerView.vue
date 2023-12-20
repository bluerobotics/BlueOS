<template>
  <v-container fluid>
    <pull-progress
      :progress="pull_output"
      :show="show_pull_output"
      :download="download_percentage"
      :extraction="extraction_percentage"
      :statustext="status_text"
    />
    <v-dialog
      v-model="show_dialog"
      width="80%"
    >
      <extension-modal
        :extension="selected_extension"
        :installed="installedVersion()"
        @clicked="installFromSelected"
      />
    </v-dialog>
    <v-dialog
      v-model="show_log"
      width="80%"
    >
      <v-card>
        <v-card-text>
          <!-- eslint-disable -->
          <pre class="logs" v-html="log_output" />
          <!-- eslint-enable -->
        </v-card-text>
      </v-card>
    </v-dialog>
    <v-tabs
      v-model="tab"
      fixed-tabs
    >
      <v-tab>
        <v-icon class="mr-5">
          mdi-store-search
        </v-icon>
        Store
      </v-tab>
      <v-tab>
        <v-icon class="mr-5">
          mdi-bookshelf
        </v-icon>
        Installed
      </v-tab>
    </v-tabs>
    <v-card
      v-if="tab === 0"
      class="d-flex pa-5"
    >
      <v-card min-width="200px">
        <v-list>
          <v-list-item-subtitle class="pa-3 font-weight-bold">
            Provider
          </v-list-item-subtitle>
          <v-checkbox
            v-for="(name, index) in providers"
            :key="`provider-${index}`"
            v-model="selected_companies"
            :label="name"
            :value="name"
            class="pa-0 pl-3 ma-0"
          />
          <v-divider class="ma-3" />
          <v-list-item-subtitle class="pa-3 font-weight-bold">
            Type
          </v-list-item-subtitle>
          <v-checkbox
            v-for="(name, index) in tags"
            :key="`tag-${index}`"
            v-model="selected_tags"
            :label="name"
            :value="name"
            class="pa-0 pl-3 ma-0"
          />
        </v-list>
      </v-card>
      <v-row
        dense
        class="d-flex justify-space-between"
      >
        <extension-card
          v-for="extension in filteredManifest"
          :key="extension.identifier + extension.name"
          :extension="extension"
          class="ma-2"
          @clicked="showModal(extension)"
        />
      </v-row>
      <v-container
        v-if="manifest.length === 0"
        class="text-center"
      >
        <p class="text-h6">
          No Extensions available. Make sure the vehicle has internet access and try again.
        </p>
      </v-container>
    </v-card>
    <v-card
      v-if="tab === 1"
      class="d-flex pa-5"
      text-align="center"
    >
      <div v-if="tab === 1" class="installed-extensions-container">
        <installed-extension-card
          v-for="extension in installed_extensions"
          :key="extension.docker"
          :extension="extension"
          :loading="extension.loading"
          :metrics="metricsFor(extension)"
          :container="getContainer(extension)"
          :versions="remoteVersions(extension)"
          :extension-data="remoteVersions(extension)"
          class="installed-extension-card"
          @edit="openEditDialog"
          @showlogs="showLogs(extension)"
          @uninstall="uninstall(extension)"
          @disable="disable(extension)"
          @enable="enableAndStart(extension)"
          @restart="restart(extension)"
          @update="update"
        />
      </div>
      <template
        v-if="Object.keys(installed_extensions).isEmpty()"
      >
        <p v-if="dockers_fetch_failed" class="text-h6" style="margin: auto;">
          Failed to fetch installed extensions. Make sure the vehicle has internet access and try again.
        </p>
        <p
          v-else-if="dockers_fetch_done"
          class="text-h6"
        >
          No Extensions installed.
        </p>
        <template v-else>
          <spinning-logo size="20%" subtitle="Fetching installed extensions" />
        </template>
      </template>
      <v-fab-transition>
        <v-btn
          :key="'create_button'"
          color="primary"
          fab
          large
          dark
          fixed
          bottom
          right
          class="v-btn--example"
          @click="openCreationDialog"
        >
          <v-icon>mdi-plus</v-icon>
        </v-btn>
      </v-fab-transition>
      <creation-dialog
        v-if="edited_extension"
        :extension="edited_extension"
        @extensionChange="createOrUpdateExtension"
        @closed="clearEditedExtension"
      />
    </v-card>
  </v-container>
</template>

<script lang="ts">
import AnsiUp from 'ansi_up'
import axios from 'axios'
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import ExtensionCard from '@/components/kraken/ExtensionCard.vue'
import CreationDialog from '@/components/kraken/ExtensionCreationDialog.vue'
import ExtensionModal from '@/components/kraken/ExtensionModal.vue'
import InstalledExtensionCard from '@/components/kraken/InstalledExtensionCard.vue'
import PullProgress from '@/components/utils/PullProgress.vue'
import Notifier from '@/libs/notifier'
import { Dictionary } from '@/types/common'
import { kraken_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import PullTracker from '@/utils/pull_tracker'

import {
  ExtensionData, InstalledExtensionData, RunningContainer, Version,
} from '../types/kraken'

const API_URL = '/kraken/v1.0'

const notifier = new Notifier(kraken_service)

export default Vue.extend({
  name: 'ExtensionManagerView',
  components: {
    ExtensionCard,
    InstalledExtensionCard,
    ExtensionModal,
    PullProgress,
    CreationDialog,
    SpinningLogo,
  },
  data() {
    return {
      tab: 0,
      show_dialog: false,
      installed_extensions: {} as Dictionary<InstalledExtensionData>,
      selected_extension: null as (null | ExtensionData),
      selected_companies: [] as string[],
      selected_tags: [] as string[],
      running_containers: [] as RunningContainer[],
      manifest: [] as ExtensionData[],
      dockers_fetch_done: false,
      dockers_fetch_failed: false,
      show_pull_output: false,
      pull_output: '',
      download_percentage: 0,
      extraction_percentage: 0,
      status_text: '',
      log_output: null as null | string,
      show_log: false,
      metrics: {} as Dictionary<{ cpu: number, memory: number}>,
      metrics_interval: 0,
      edited_extension: null as null | InstalledExtensionData,
    }
  },
  computed: {
    providers(): string[] {
      const authors = this.manifest
        .map((extension) => this.newestVersion(extension.versions)?.company?.name ?? 'unknown').sort() as string[]
      return [...new Set(authors)]
    },
    tags(): string[] {
      const authors = this.manifest
        .map((extension) => this.newestVersion(extension.versions)?.type ?? 'unknown')
        .sort() as string[]
      return [...new Set(authors)]
    },
    filteredManifest(): ExtensionData[] {
      if (this.selected_companies.isEmpty() && this.selected_tags.isEmpty()) {
        // By default we remove examples if nothing is selected
        return this.manifest.filter((extension) => this.newestVersion(extension.versions)?.type !== 'example')
      }

      let { manifest } = this

      if (!this.selected_companies.isEmpty()) {
        manifest = manifest.filter((extension) => this.newestVersion(extension.versions)?.company?.name !== undefined)
          .filter((extension) => this.selected_companies
            .includes(this.newestVersion(extension.versions)?.company?.name ?? ''))
      }

      if (this.selected_tags.isEmpty()) {
        return manifest
      }

      return manifest
        .filter((extension) => this.newestVersion(extension.versions)?.type !== undefined)
        .filter((extension) => this.selected_tags
          .includes(this.newestVersion(extension.versions)?.type ?? ''))
    },
  },
  mounted() {
    this.fetchManifest()
    this.fetchInstalledExtensions()
    this.fetchMetrics()
    this.metrics_interval = setInterval(this.fetchMetrics, 30000)
  },
  destroyed() {
    clearInterval(this.metrics_interval)
  },
  methods: {
    newestVersion(versions: Dictionary<Version>): Version | undefined {
      return Object.values(versions)?.[0] as Version | undefined
    },
    clearEditedExtension() {
      this.edited_extension = null
    },
    async update(extension: InstalledExtensionData, version: string) {
      this.show_pull_output = true
      const tracker = new PullTracker(
        () => {
          setTimeout(() => {
            this.show_pull_output = false
          }, 1000)
        },
        (error) => {
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        },
      )
      await back_axios({
        url: `${API_URL}/extension/update_to_version`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
          new_version: version,
        },
        timeout: 120000,
        onDownloadProgress: (progressEvent) => {
          tracker.digestNewData(progressEvent)
          this.pull_output = tracker.pull_output
          this.download_percentage = tracker.download_percentage
          this.extraction_percentage = tracker.extraction_percentage
          this.status_text = tracker.overall_status
        },
      })
        .then(() => {
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        })
        .finally(() => {
          this.show_pull_output = false
          this.show_dialog = false
          this.pull_output = ''
          this.download_percentage = 0
          this.extraction_percentage = 0
          this.status_text = ''
        })
    },
    metricsFor(extension: InstalledExtensionData): { cpu: number, memory: number} | Record<string, never> {
      const name = this.getContainerName(extension)?.replace('/', '')
      return name ? this.metrics[name] : {}
    },
    async createOrUpdateExtension(): Promise<void> {
      if (!this.edited_extension) {
        // TODO: error
        return
      }
      await this.install(
        this.edited_extension.identifier,
        this.edited_extension.name,
        this.edited_extension.docker,
        this.edited_extension.tag,
        true,
        this.edited_extension?.permissions ?? '',
        this.edited_extension?.user_permissions ?? '',
      )
      this.show_dialog = false
      this.edited_extension = null
    },
    openEditDialog(extension: InstalledExtensionData): void {
      this.edited_extension = extension
    },
    openCreationDialog() : void {
      this.edited_extension = {
        identifier: 'yourorganization.yourextension',
        name: '',
        docker: '',
        enabled: true,
        tag: '',
        permissions: '{}',
        user_permissions: '{}',
      }
    },
    getContainer(extension: InstalledExtensionData): RunningContainer | undefined {
      return this.running_containers?.find(
        (container) => container.image === `${extension.docker}:${extension.tag}`,
      )
    },
    async fetchMetrics(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/stats`,
        timeout: 20000,
      })
        .then((response) => {
          this.metrics = response.data
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_METRICS_FETCH_FAIL', error)
        })
      await back_axios({
        method: 'get',
        url: `${API_URL}/list_containers`,
        timeout: 30000,
      })
        .then((response) => {
          this.running_containers = response.data ?? []
        })
        .catch((error) => {
          notifier.pushBackError('RUNNING_CONTAINERS_FETCH_FAIL', error)
        })
    },
    getContainerName(extension: InstalledExtensionData): string | null {
      return this.getContainer(extension)?.name ?? null
    },
    async fetchManifest(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/extensions_manifest`,
        timeout: 3000,
      })
        .then((response) => {
          if ('detail' in response.data) {
            notifier.pushBackError('EXTENSIONS_MANIFEST_FETCH_FAIL', new Error(response.data.detail))
            return
          }
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
          this.installed_extensions = {}
          for (const extension of response.data) {
            this.installed_extensions[extension.identifier] = extension
          }
          this.dockers_fetch_failed = false
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_INSTALLED_FETCH_FAIL', error)
          this.dockers_fetch_failed = true
        })
        .finally(() => {
          this.dockers_fetch_done = true
        })
    },
    async showLogs(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      const ansi = new AnsiUp()
      this.log_output = ''

      back_axios({
        method: 'get',
        url: `${API_URL}/log`,
        params: {
          container_name: this.getContainerName(extension),
        },
        onDownloadProgress: (progressEvent) => {
          const chunk = progressEvent.currentTarget.response
          this.$set(this, 'log_output', ansi.ansi_to_html(chunk))
          this.show_log = true
          this.setLoading(extension, false)
          this.$nextTick(() => {
            // TODO: find a better way to scroll to bottom
            const output = document.querySelector(
              '#app > div.v-dialog__content.v-dialog__content--active > div',
            ) as HTMLInputElement
            if (!output) {
              return
            }
            output.scrollTop = output.scrollHeight
          })
        },
        timeout: 30000,
      })
        .then(() => {
          this.setLoading(extension, false)
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_LOG_FETCH_FAIL', error)
        })
        .finally(() => {
          this.setLoading(extension, false)
        })
    },
    showModal(extension: ExtensionData) {
      this.show_dialog = true
      this.selected_extension = extension
    },
    async install(
      identifier: string,
      name: string,
      docker: string,
      tag: string,
      enabled: boolean,
      permissions: string,
      user_permissions: string,
    ) {
      this.show_dialog = false
      this.show_pull_output = true
      const tracker = new PullTracker(
        () => {
          setTimeout(() => {
            this.show_pull_output = false
          }, 1000)
        },
        (error) => {
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
          this.show_pull_output = false
        },
      )

      await back_axios({
        url: `${API_URL}/extension/install`,
        method: 'POST',
        data: {
          identifier,
          name,
          docker,
          tag,
          enabled,
          permissions,
          user_permissions,
        },
        onDownloadProgress: (progressEvent) => {
          tracker.digestNewData(progressEvent)
          this.pull_output = tracker.pull_output
          this.download_percentage = tracker.download_percentage
          this.extraction_percentage = tracker.extraction_percentage
          this.status_text = tracker.overall_status
        },
      })
        .then(() => {
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        })
        .finally(() => {
          this.show_pull_output = false
          this.show_dialog = false
          this.pull_output = ''
          this.download_percentage = 0
          this.extraction_percentage = 0
          this.status_text = ''
        })
    },
    async installFromSelected(tag: string) {
      if (!this.selected_extension) {
        return
      }
      await this.install(
        this.selected_extension?.identifier,
        this.selected_extension?.name,
        this.selected_extension?.docker,
        tag,
        true,
        JSON.stringify(this.selected_extension?.versions[tag].permissions),
        '',
      )
    },
    async uninstall(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      await axios.post(`${API_URL}/extension/uninstall`, null, {
        params: {
          extension_identifier: extension.identifier,
        },
      })
        .then(() => {
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_UNINSTALL_FAIL', error)
        })
      this.setLoading(extension, false)
    },
    installedVersion(): string | undefined {
      const extension_identifier = this.selected_extension?.identifier
      if (!extension_identifier) {
        return undefined
      }
      return this.installed_extensions[extension_identifier]?.tag
    },
    async disable(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      delete this.metrics[this.getContainerName(extension)?.replace('/', '') ?? '']
      this.running_containers = this.running_containers.filter(
        (container) => container.name !== this.getContainerName(extension),
      )
      await back_axios({
        url: `${API_URL}/extension/disable`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
        },
        timeout: 2000,
      })
        .catch((error) => {
          notifier.pushBackError('EXTENSION_DISABLE_FAIL', error)
        })
      this.fetchInstalledExtensions()
      this.setLoading(extension, false)
      this.fetchMetrics()
    },
    async enableAndStart(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      await back_axios({
        url: `${API_URL}/extension/enable`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
        },
        timeout: 2000,
      })
        .catch((error) => {
          notifier.pushBackError('EXTENSION_ENABLE_FAIL', error)
        })
      this.fetchInstalledExtensions()
      this.setLoading(extension, false)
      this.fetchMetrics()
    },
    async restart(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      await back_axios({
        url: `${API_URL}/extension/restart`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
        },
        timeout: 2000,
      })
        .then((response) => {
          this.running_containers = response.data
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSION_RESTART_FAIL', error)
        })
      this.fetchInstalledExtensions()
      this.setLoading(extension, false)
      this.fetchMetrics()
    },
    remoteVersions(extension: InstalledExtensionData): ExtensionData | undefined {
      return this.manifest.find(
        (remoteExtension: ExtensionData) => remoteExtension.identifier === extension.identifier,
      )
    },
    setLoading(extension: InstalledExtensionData, loading: boolean) {
      this.installed_extensions[extension.identifier].loading = loading
      Vue.set(this.installed_extensions, extension.identifier, this.installed_extensions[extension.identifier])
    },
  },
})
</script>

<style>
.installed-extensions-container {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
}

.installed-extension-card {
  margin: 10px;
  flex: 1 1 400px;
}

.jv-code {
  padding: 0px !important;
}

pre.logs {
  color:white;
  background: black;
  padding: 15px;
  overflow-x: scroll;
}
</style>
