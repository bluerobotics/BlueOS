<template>
  <v-container fluid>
    <not-safe-overlay />
    <pull-progress
      :progress="pull_output"
      :show="show_pull_output"
      :download="download_percentage"
      :extraction="extraction_percentage"
      :statustext="status_text"
    />
    <v-dialog
      v-model="show_dialog"
      max-width="800px"
    >
      <ExtensionDetailsModal
        :extension="selected_extension"
        :installed="installedVersion()"
        :installed-extension="installedExtension()"
        @clicked="performActionFromModal"
      />
    </v-dialog>
    <ExtensionSettingsModal
      v-model="show_settings"
      @refresh="fetchManifest"
    />
    <v-dialog
      v-model="show_log"
      width="80%"
    >
      <v-card>
        <v-app-bar dense>
          <v-spacer />
          <v-toolbar-title>
            {{ log_info_output }}
          </v-toolbar-title>
          <v-spacer />
          <v-checkbox
            v-model="follow_logs"
            label="Follow Logs"
            hide-details
          />
        </v-app-bar>
        <v-sheet>
          <v-card-text ref="logContainer" class="scrollable-content">
            <!-- eslint-disable -->
            <pre class="logs" v-html="log_output" />
            <!-- eslint-enable -->
          </v-card-text>
        </v-sheet>
      </v-card>
    </v-dialog>
    <v-toolbar>
      <v-spacer />
      <v-tabs
        v-model="tab"
        fixed-tabs
      >
        <v-tab key="0" href="#0" class="tab-text">
          <v-icon class="mr-3">
            {{ settings.is_dev_mode ? 'mdi-incognito' : 'mdi-store-search' }}
          </v-icon>
          {{ settings.is_dev_mode ? 'Back Alley' : 'Store' }}
        </v-tab>
        <v-tab v-if="settings.is_dev_mode" key="1" href="#1" class="tab-text">
          <v-icon class="mr-3">
            mdi-package-variant
          </v-icon>
          Bazaar
        </v-tab>
        <v-tab key="2" href="#2" class="tab-text">
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
    <v-dialog
      v-model="alerter"
      width="30%"
      dimissable
    >
      <v-alert
        type="error"
        variant="tonal"
        class="mb-0"
      >
        {{ alerter_error }}
      </v-alert>
    </v-dialog>
    <BackAlleyTab
      v-show="is_back_alley_tab"
      :manifest="manifest"
      :installed-extensions="installed_extensions"
      @clicked="showModal"
      @update="update"
    />
    <BazaarTab
      v-show="is_bazaar_tab"
    />
    <v-card
      v-if="is_installed_tab"
      class="pa-5 main-container"
      text-align="center"
    >
      <div class="installed-extension-card">
        <div class="installed-extensions-container">
          <InstalledExtensionCard
            v-for="extension in installed_extensions"
            :key="extension.docker"
            :extension="extension"
            :loading="extension.loading"
            :metrics="metricsFor(extension)"
            :container="getContainer(extension)"
            :versions="remoteVersions(extension)"
            :extension-data="remoteVersions(extension)"
            @edit="openEditDialog"
            @showlogs="showLogs(extension)"
            @uninstall="uninstall(extension)"
            @disable="disable(extension)"
            @enable="enableAndStart(extension)"
            @restart="restart(extension)"
            @update="update"
          />
        </div>
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
      <ExtensionCreationModal
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
import axios, { CancelTokenSource } from 'axios'
import Vue from 'vue'

import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import SpinningLogo from '@/components/common/SpinningLogo.vue'
import BackAlleyTab from '@/components/kraken/BackAlleyTab.vue'
import BazaarTab from '@/components/kraken/BazaarTab.vue'
import InstalledExtensionCard from '@/components/kraken/cards/InstalledExtensionCard.vue'
import kraken from '@/components/kraken/KrakenManager'
import ExtensionCreationModal from '@/components/kraken/modals/ExtensionCreationModal.vue'
import ExtensionDetailsModal from '@/components/kraken/modals/ExtensionDetailsModal.vue'
import ExtensionSettingsModal from '@/components/kraken/modals/ExtensionSettingsModal.vue'
import PullProgress from '@/components/utils/PullProgress.vue'
import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import { OneMoreTime } from '@/one-more-time'
import { Dictionary } from '@/types/common'
import { kraken_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import PullTracker from '@/utils/pull_tracker'
import { aggregateStreamingResponse, parseStreamingResponse } from '@/utils/streaming'

import {
  ExtensionData, InstalledExtensionData, RunningContainer,
} from '../types/kraken'

const API_URL = '/kraken/v1.0'

const notifier = new Notifier(kraken_service)

export default Vue.extend({
  name: 'ExtensionManagerView',
  components: {
    BazaarTab,
    BackAlleyTab,
    InstalledExtensionCard,
    ExtensionDetailsModal,
    ExtensionSettingsModal,
    PullProgress,
    ExtensionCreationModal,
    SpinningLogo,
    NotSafeOverlay,
  },
  data() {
    return {
      tab: '0',
      alerter: false,
      alerter_error: '',
      settings,
      show_dialog: false,
      show_settings: false,
      installed_extensions: {} as Dictionary<InstalledExtensionData>,
      selected_extension: null as (null | ExtensionData),
      running_containers: [] as RunningContainer[],
      manifest: undefined as undefined | string | ExtensionData[],
      dockers_fetch_done: false,
      dockers_fetch_failed: false,
      show_pull_output: false,
      pull_output: '',
      download_percentage: 0,
      extraction_percentage: 0,
      status_text: '',
      show_log: false,
      follow_logs: true,
      log_abort_controller: null as null | CancelTokenSource,
      log_output: null as null | string,
      log_info_output: null as null | string,
      metrics: {} as Dictionary<{ cpu: number, memory: number}>,
      metrics_interval: 0,
      edited_extension: null as null | InstalledExtensionData & { editing: boolean },
      fetch_installed_ext_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_running_containers_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_containers_stats_task: new OneMoreTime({ delay: 25000, disposeWith: this }),
    }
  },
  computed: {
    is_back_alley_tab(): boolean {
      return this.tab === '0'
    },
    is_bazaar_tab(): boolean {
      return this.tab === '1'
    },
    is_installed_tab(): boolean {
      return this.tab === '2'
    },
    manifest_as_data(): ExtensionData[] {
      if (this.manifest === undefined || typeof this.manifest === 'string') {
        return []
      }

      return this.manifest as ExtensionData[]
    },
  },
  watch: {
    show_log: {
      handler(val) {
        if (!val) {
          this.log_abort_controller?.cancel()
        }
      },
      immediate: true,
    },
    follow_logs: {
      handler(val) {
        if (val) {
          const logContainer = this.$refs.logContainer as HTMLElement
          if (logContainer) {
            logContainer.scrollTop = logContainer.scrollHeight
          }
        }
      },
    },
  },
  mounted() {
    this.fetchManifest()
    this.fetch_installed_ext_task.setAction(this.fetchInstalledExtensions)
    this.fetch_running_containers_task.setAction(this.fetchRunningContainers)
    this.fetch_containers_stats_task.setAction(this.fetchContainersStats)
  },
  destroyed() {
    clearInterval(this.metrics_interval)
  },
  methods: {
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
          this.alerter = true
          this.alerter_error = String(error)
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        },
      )
      back_axios({
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
          this.alerter = true
          this.alerter_error = String(error)
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
      return name ? this.metrics[name] ?? {} : {}
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
      this.edited_extension = { ...extension, editing: true }
    },
    openCreationDialog() : void {
      this.edited_extension = {
        identifier: 'yourorganization.yourextension',
        name: '',
        docker: '',
        enabled: true,
        tag: '',
        permissions: '{}',
        user_permissions: '',
        editing: false,
      }
    },
    getContainer(extension: InstalledExtensionData): RunningContainer | undefined {
      return this.running_containers?.find(
        (container) => container.image === `${extension.docker}:${extension.tag}`,
      )
    },
    async fetchRunningContainers(): Promise<void> {
      back_axios({
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
    async fetchContainersStats(): Promise<void> {
      back_axios({
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
    },
    getContainerName(extension: InstalledExtensionData): string | null {
      return this.getContainer(extension)?.name ?? null
    },
    async fetchManifest(): Promise<void> {
      this.manifest = undefined

      try {
        this.manifest = await kraken.fetchConsolidatedManifests()
      } catch (error) {
        this.manifest = String(error)
      }
    },
    async fetchInstalledExtensions(): Promise<void> {
      back_axios({
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
      this.log_abort_controller = axios.CancelToken.source()
      this.log_output = ''
      this.log_info_output = `Awaiting logs for ${extension.name}`
      this.show_log = true
      let outputBuffer = ''

      const containerName = `extension-${(extension.docker + extension.tag).replace(/[^a-zA-Z0-9]/g, '')}`
      const fetchLogs = (): void => {
        const ansi = new AnsiUp()
        let lastDecode = ''

        back_axios({
          method: 'get',
          url: `${API_URL}/log`,
          params: {
            container_name: containerName,
          },
          onDownloadProgress: (progressEvent) => {
            const result = aggregateStreamingResponse(
              parseStreamingResponse(progressEvent.currentTarget.response),
              (_, buffer) => Boolean(buffer),
            )

            if (result) {
              lastDecode = ansi.ansi_to_html(result)
              this.log_info_output = `Logs for ${extension.name}`
              this.$set(this, 'log_output', outputBuffer + lastDecode)
            }
            this.$nextTick(() => {
              const logContainer = this.$refs.logContainer as HTMLElement
              if (this.follow_logs && logContainer) {
                logContainer.scrollTop = logContainer.scrollHeight
              }
            })
          },
          cancelToken: this.log_abort_controller?.token,
        })
          .then(() => {
            outputBuffer += lastDecode
            this.log_info_output = `Reconnecting to ${extension.name}`
            setTimeout(fetchLogs, 500)
          })
          .catch((error) => {
            if (axios.isCancel(error)) {
              return
            }

            notifier.pushBackError('EXTENSIONS_LOGS_FETCH_FAIL', error)
          })
      }

      fetchLogs()
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
          this.alerter = true
          this.alerter_error = String(error)
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
          this.show_pull_output = false
        },
      )

      back_axios({
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
          this.alerter = true
          this.alerter_error = String(error)
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
    async performActionFromModal(
      identifier: string,
      tag: string,
      permissions: string | undefined,
      isInstalled: boolean,
    ) {
      if (isInstalled) {
        const ext = this.installed_extensions[identifier]
        if (!ext) {
          return
        }
        this.show_dialog = false
        await this.uninstall(ext)
      } else {
        await this.installFromSelected(tag, permissions)
      }
    },
    async installFromSelected(tag: string, permissions: string | undefined) {
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
        permissions ?? '',
      )
    },
    async uninstall(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      axios.post(`${API_URL}/extension/uninstall`, null, {
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
        .finally(() => {
          this.setLoading(extension, false)
        })
    },
    installedExtension(): InstalledExtensionData | undefined {
      const extension_identifier = this.selected_extension?.identifier
      if (!extension_identifier) {
        return undefined
      }
      return this.installed_extensions[extension_identifier]
    },
    installedVersion(): string | undefined {
      const installed_extension = this.installedExtension()
      return installed_extension?.tag
    },
    async disable(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      delete this.metrics[this.getContainerName(extension)?.replace('/', '') ?? '']
      this.running_containers = this.running_containers.filter(
        (container) => container.name !== this.getContainerName(extension),
      )
      back_axios({
        url: `${API_URL}/extension/disable`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
        },
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('EXTENSION_DISABLE_FAIL', error)
        })
        .finally(() => {
          this.fetchInstalledExtensions()
          this.setLoading(extension, false)
        })
    },
    async enableAndStart(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      back_axios({
        url: `${API_URL}/extension/enable`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
        },
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('EXTENSION_ENABLE_FAIL', error)
        })
        .finally(() => {
          this.fetchInstalledExtensions()
          this.fetchRunningContainers()
          this.fetchContainersStats()
          this.setLoading(extension, false)
        })
    },
    async restart(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      back_axios({
        url: `${API_URL}/extension/restart`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
        },
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('EXTENSION_RESTART_FAIL', error)
        })
        .finally(() => {
          this.fetchInstalledExtensions()
          this.fetchRunningContainers()
          this.setLoading(extension, false)
        })
    },
    remoteVersions(extension: InstalledExtensionData): ExtensionData | undefined {
      return this.manifest_as_data.find(
        (remoteExtension: ExtensionData) => remoteExtension.identifier === extension.identifier,
      )
    },
    setLoading(extension: InstalledExtensionData, loading: boolean) {
      const temp = { ...this.installed_extensions }
      temp[extension.identifier].loading = loading
      this.installed_extensions = temp
    },
  },
})
</script>

<style>
.main-container {
  background-color: #135DA355 !important;
}

.installed-extensions-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(445px, 1fr));
  gap: 15px;
  justify-content: center;
}

@media (max-width: 994px) {
  .installed-extensions-container {
    display: flex;
    flex-direction: column;
    align-items: center;
  }
}

.installed-extension-card {
  padding: 10px;
}

.jv-code {
  padding: 0px !important;
}

pre.logs {
  color:white;
  background: black;
  padding: 10px;
  overflow-x: scroll;
}

.search-container {
  flex: 1 1 auto;
  width: 50% !important;
}

.tabs-container-spacer-right {
  flex: 1 1 auto;
  width: 30% !important;
}

.tab-text {
  white-space: nowrap !important;
}

.scrollable-content {
  max-height: calc(80vh - 64px);
  overflow-y: auto;
}
</style>
