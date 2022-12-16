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
          <pre class="logs">
            {{ log_output }}
          </pre>
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
    <div
      v-if="tab === 0"
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
        v-if="tab === 1"
        class="pa-6"
      >
        <v-row
          dense
        >
          <v-col
            v-for="extension in installed_extensions"
            :key="extension.docker"
            class="pa-2 col-6"
          >
            <installed-extension-card
              :extension="extension"
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
          :extension="edited_extension"
          @extensionChange="createOrUpdateExtension"
        />
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

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

import { ExtensionData, InstalledExtensionData, RunningContainer } from '../types/kraken'

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
    async update(extension: InstalledExtensionData, version: string) {
      this.show_pull_output = true
      const tracker = new PullTracker(() => {
        setTimeout(() => {
          this.show_pull_output = false
        }, 1000)
      })
      await back_axios({
        url: `${API_URL}/extension/update_to_version`,
        method: 'POST',
        params: {
          extension_identifier: extension.identifier,
          version,
        },
        timeout: 20000,
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
        tag: '',
        permissions: '{}',
        user_permissions: '{}',
      }
    },
    getContainer(extension: InstalledExtensionData): RunningContainer | undefined {
      return this.running_containers?.filter(
        (container) => container.image === `${extension.docker}:${extension.tag}`,
      ).first()
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
    async showLogs(extension: InstalledExtensionData): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/log`,
        params: {
          container_name: this.getContainerName(extension),
        },
        timeout: 30000,
      })
        .then((response) => {
          this.log_output = response.data.join('')
          this.show_log = true
        })
        .catch((error) => {
          notifier.pushBackError('EXTENSIONS_LOG_FETCH_FAIL', error)
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
      const tracker = new PullTracker(() => {
        setTimeout(() => {
          this.show_pull_output = false
        }, 1000)
      })

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
    async uninstall(extension: ExtensionData) {
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
    },
    installedVersion(): string | undefined {
      const extension_docker = this.selected_extension?.docker
      if (!extension_docker) {
        return undefined
      }
      return this.installed_extensions.find((extension) => extension.docker === extension_docker)?.tag
    },
    async disable(extension: ExtensionData) {
      // TODO: spinner
      await back_axios({
        url: `${API_URL}/extension/disable`,
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
          notifier.pushBackError('EXTENSION_DISABLE_FAIL', error)
        })
      this.fetchInstalledExtensions()
      this.fetchMetrics()
    },
    async enableAndStart(extension: ExtensionData) {
      // TODO: spinner
      await back_axios({
        url: `${API_URL}/extension/enable`,
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
          notifier.pushBackError('EXTENSION_ENABLE_FAIL', error)
        })
      this.fetchInstalledExtensions()
      this.fetchMetrics()
    },
    async restart(extension: ExtensionData) {
      // TODO: spinner
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
      this.fetchMetrics()
    },
    remoteVersions(extension: InstalledExtensionData): ExtensionData | undefined {
      return this.manifest.filter(
        (remoteExtension: ExtensionData) => remoteExtension.identifier === extension.identifier,
      ).first()
    },
  },
})
</script>

<style>
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
