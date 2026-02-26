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
      v-model="show_install_from_file_dialog"
      max-width="900px"
      scrollable
    >
      <v-card
        class="tar-upload-card"
        outlined
      >
        <v-card-title class="d-flex flex-column flex-sm-row justify-space-between align-start">
          <div>
            <div class="text-h6">
              Install extension from file
            </div>
            <div class="subtitle-2 mt-1">
              Upload a Kraken-compatible .tar archive to sideload an extension.
            </div>
          </div>
          <div class="d-flex align-center mt-4 mt-sm-0">
            <v-chip
              v-if="install_from_file_phase === 'success'"
              color="success"
              label
              small
              class="mr-2"
            >
              Installed
            </v-chip>
            <v-btn icon @click="closeInstallFromFileDialog">
              <v-icon>mdi-close</v-icon>
            </v-btn>
          </div>
        </v-card-title>
        <v-divider />
        <v-card-text>
          <v-row>
            <v-col cols="12" md="6">
              <v-file-input
                v-model="selected_tar_file"
                label="Select .tar file"
                accept=".tar"
                truncate-length="24"
                prepend-icon="mdi-file-upload-outline"
                :disabled="file_uploading || install_from_file_phase === 'installing'"
                show-size
                @change="onTarFileSelected"
              />
              <div class="tar-upload-actions mt-2">
                <v-btn
                  color="primary"
                  :disabled="!canUploadSelectedFile"
                  :loading="file_uploading"
                  @click="uploadSelectedTarFile"
                >
                  Upload file
                </v-btn>
                <v-btn
                  text
                  :disabled="file_uploading || install_from_file_phase === 'installing'"
                  @click="resetUploadFlow"
                >
                  Reset
                </v-btn>
                <v-btn
                  color="secondary"
                  :disabled="!canConfigureUploaded"
                  @click="openCreationDialogFromUpload()"
                >
                  Configure & Install
                </v-btn>
              </div>
              <v-alert
                v-if="install_from_file_error"
                type="error"
                dense
                class="mt-4"
              >
                {{ install_from_file_error }}
              </v-alert>
              <v-alert
                v-else-if="install_from_file_phase === 'success'"
                type="success"
                dense
                class="mt-4"
              >
                Extension installed successfully.
              </v-alert>
            </v-col>
            <v-col cols="12" md="6">
              <div class="upload-phase-list">
                <div
                  v-for="phase in uploadPhases"
                  :key="phase.key"
                  :class="['upload-phase', phase.status]"
                >
                  <div class="upload-phase__header">
                    <v-icon
                      small
                      class="mr-2"
                      :class="tarStepTextClass(phase.status)"
                    >
                      {{ phase.icon }}
                    </v-icon>
                    <div>
                      <div
                        class="upload-phase__title"
                        :class="tarStepTextClass(phase.status)"
                      >
                        {{ phase.label }}
                      </div>
                      <div class="text-caption text--secondary">
                        {{ phase.description }}
                      </div>
                    </div>
                  </div>
                  <v-progress-linear
                    v-if="phase.showProgress"
                    class="mt-2"
                    :value="phase.indeterminate ? undefined : phase.progress"
                    :indeterminate="phase.indeterminate"
                    :color="tarStepColor(phase.status)"
                    height="6"
                  />
                  <div
                    v-if="phase.progressText"
                    class="text-caption mt-1"
                    :class="tarStepTextClass(phase.status)"
                  >
                    {{ phase.progressText }}
                  </div>
                </div>
              </div>
            </v-col>
          </v-row>
          <v-expand-transition>
            <div
              v-if="upload_metadata"
              class="metadata-preview mt-4"
            >
              <div class="subtitle-2 mb-2">
                Detected metadata
              </div>
              <div class="metadata-preview__grid">
                <div>
                  <div class="caption text--secondary">
                    Identifier
                  </div>
                  <div class="body-2">
                    {{ upload_metadata.identifier || 'Pending' }}
                  </div>
                </div>
                <div>
                  <div class="caption text--secondary">
                    Name
                  </div>
                  <div class="body-2">
                    {{ upload_metadata.name || 'Pending' }}
                  </div>
                </div>
                <div>
                  <div class="caption text--secondary">
                    Docker
                  </div>
                  <div class="body-2">
                    {{ upload_metadata.docker || 'Pending' }}
                  </div>
                </div>
                <div>
                  <div class="caption text--secondary">
                    Tag
                  </div>
                  <div class="body-2">
                    {{ upload_metadata.tag || 'latest' }}
                  </div>
                </div>
              </div>
            </div>
          </v-expand-transition>
        </v-card-text>
        <v-card-actions class="justify-end">
          <v-btn text @click="closeInstallFromFileDialog">
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <ExtensionLogsModal
      v-model="show_log"
      :extension-identifier="selected_log_extension_identifier"
      :extension-name="selected_log_extension_name"
      :zenoh-session="zenoh_session"
    />
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
      @refresh="fetchManifest"
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
        <v-speed-dial
          :key="'create_button'"
          v-model="fab_menu"
          fixed
          bottom
          right
          direction="top"
          transition="slide-y-reverse-transition"
        >
          <template #activator>
            <v-btn
              v-model="fab_menu"
              color="primary"
              fab
              large
              dark
            >
              <v-icon v-if="fab_menu">
                mdi-close
              </v-icon>
              <v-icon v-else>
                mdi-plus
              </v-icon>
            </v-btn>
          </template>
          <v-btn
            v-tooltip="'Install from file'"
            fab
            dark
            small
            color="primary"
            @click="openInstallFromFileDialog"
          >
            <v-icon>mdi-file-upload-outline</v-icon>
          </v-btn>
          <v-btn
            v-tooltip="'Create from scratch'"
            fab
            dark
            small
            color="green"
            @click="openCreationDialog"
          >
            <v-icon>mdi-code-braces</v-icon>
          </v-btn>
        </v-speed-dial>
      </v-fab-transition>
      <ExtensionCreationModal
        v-if="edited_extension"
        :extension="edited_extension"
        :temp-tag="upload_temp_tag"
        @extensionChange="createOrUpdateExtension"
        @closed="clearEditedExtension"
      />
    </v-card>
  </v-container>
</template>

<script lang="ts">
import {
  Config, Session,
} from '@eclipse-zenoh/zenoh-ts'
import Vue from 'vue'

import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import SpinningLogo from '@/components/common/SpinningLogo.vue'
import BackAlleyTab from '@/components/kraken/BackAlleyTab.vue'
import BazaarTab from '@/components/kraken/BazaarTab.vue'
import InstalledExtensionCard from '@/components/kraken/cards/InstalledExtensionCard.vue'
import kraken from '@/components/kraken/KrakenManager'
import ExtensionCreationModal from '@/components/kraken/modals/ExtensionCreationModal.vue'
import ExtensionDetailsModal from '@/components/kraken/modals/ExtensionDetailsModal.vue'
import ExtensionLogsModal from '@/components/kraken/modals/ExtensionLogsModal.vue'
import ExtensionSettingsModal from '@/components/kraken/modals/ExtensionSettingsModal.vue'
import PullProgress from '@/components/utils/PullProgress.vue'
import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import { OneMoreTime } from '@/one-more-time'
import { Dictionary } from '@/types/common'
import { kraken_service } from '@/types/frontend_services'
import PullTracker from '@/utils/pull_tracker'

import {
  ExtensionData, ExtensionUploadMetadata, InstalledExtensionData, RunningContainer,
  StreamProgressEvent, UploadProgressEvent,
} from '../types/kraken'

type TarInstallPhase = 'idle' | 'selected' | 'uploading' | 'processing' | 'ready' | 'installing' | 'success' | 'error'
type TarStepKey = 'upload' | 'load' | 'configure' | 'install'
type TarStepStatus = 'pending' | 'active' | 'complete' | 'error'

interface UploadPhaseDescriptor {
  key: TarStepKey
  label: string
  description: string
  icon: string
  status: TarStepStatus
  showProgress?: boolean
  progress?: number
  indeterminate?: boolean
  progressText?: string
}

const TAR_PHASE_LEVEL: Record<Exclude<TarInstallPhase, 'error'>, number> = {
  idle: -1,
  selected: 0,
  uploading: 0,
  processing: 1,
  ready: 2,
  installing: 3,
  success: 4,
}

const TAR_STEP_ORDER: TarStepKey[] = ['upload', 'load', 'configure', 'install']

function currentStepForPhase(phase: TarInstallPhase): TarStepKey {
  switch (phase) {
    case 'processing':
      return 'load'
    case 'ready':
      return 'configure'
    case 'installing':
    case 'success':
      return 'install'
    default:
      return 'upload'
  }
}

const notifier = new Notifier(kraken_service)

export default Vue.extend({
  name: 'ExtensionManagerView',
  components: {
    BazaarTab,
    BackAlleyTab,
    InstalledExtensionCard,
    ExtensionDetailsModal,
    ExtensionLogsModal,
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
      show_install_from_file_dialog: false,
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
      selected_log_extension_identifier: '',
      selected_log_extension_name: '',
      metrics: {} as Dictionary<{ cpu: number, memory: number}>,
      metrics_interval: 0,
      edited_extension: null as null | InstalledExtensionData & { editing: boolean },
      fetch_installed_ext_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_running_containers_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_containers_stats_task: new OneMoreTime({ delay: 25000, disposeWith: this }),
      fab_menu: false,
      upload_temp_tag: null as null | string,
      upload_metadata: null as null | ExtensionUploadMetadata,
      upload_keep_alive_task: null as null | OneMoreTime,
      selected_tar_file: null as null | File,
      file_uploading: false,
      install_from_file_phase: 'idle' as TarInstallPhase,
      install_from_file_upload_progress: 0,
      install_from_file_install_progress: 0,
      install_from_file_status_text: '',
      install_from_file_error: null as null | string,
      install_from_file_failed_step: null as null | TarStepKey,
      install_from_file_last_level: -1,
      zenoh_session: null as Session | null,
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
    canUploadSelectedFile(): boolean {
      return Boolean(
        this.selected_tar_file
        && !this.file_uploading
        && this.install_from_file_phase !== 'installing'
        && this.install_from_file_phase !== 'processing',
      )
    },
    canConfigureUploaded(): boolean {
      return this.install_from_file_phase === 'ready' && Boolean(this.upload_metadata && this.upload_temp_tag)
    },
    uploadPhases(): UploadPhaseDescriptor[] {
      const uploadStatus = this.getTarStepStatus('upload')
      const loadStatus = this.getTarStepStatus('load')
      const configureStatus = this.getTarStepStatus('configure')
      const installStatus = this.getTarStepStatus('install')

      const installProgress = Number.isFinite(this.install_from_file_install_progress)
        ? this.install_from_file_install_progress
        : 0

      let uploadProgressText: string | undefined
      if (uploadStatus === 'complete') {
        uploadProgressText = 'Upload finished'
      } else if (uploadStatus === 'active' && this.install_from_file_upload_progress > 0) {
        uploadProgressText = `${Math.round(this.install_from_file_upload_progress)}%`
      }

      return [
        {
          key: 'upload',
          label: 'Upload file',
          description: 'Upload extension .tar file to onboard computer',
          icon: 'mdi-upload',
          status: uploadStatus,
          showProgress: true,
          progress: this.install_from_file_upload_progress,
          indeterminate: uploadStatus === 'active' && !this.install_from_file_upload_progress,
          progressText: uploadProgressText,
        },
        {
          key: 'load',
          label: 'Load Docker image',
          description: 'Import extension image and inspect metadata',
          icon: 'mdi-docker',
          status: loadStatus,
          showProgress: true,
          progress: loadStatus === 'complete' ? 100 : 0,
          indeterminate: loadStatus === 'active',
          progressText: loadStatus === 'complete' ? 'Image ready' : undefined,
        },
        {
          key: 'configure',
          label: 'Configure metadata',
          description: 'Review identifier, name, and permissions',
          icon: 'mdi-clipboard-text-edit',
          status: configureStatus,
        },
        {
          key: 'install',
          label: 'Install extension',
          description: 'Finalize extension installation',
          icon: 'mdi-progress-download',
          status: installStatus,
          showProgress: true,
          progress: installStatus === 'complete' ? 100 : installProgress,
          indeterminate: installStatus === 'active' && !installProgress,
          progressText: this.install_from_file_status_text || undefined,
        },
      ]
    },
  },
  watch: {
    show_install_from_file_dialog(val: boolean) {
      if (!val) {
        this.resetUploadFlow()
      }
    },
  },
  async mounted() {
    this.fetchManifest()
    this.fetch_installed_ext_task.setAction(this.fetchInstalledExtensions)
    this.fetch_running_containers_task.setAction(this.fetchRunningContainers)
    this.fetch_containers_stats_task.setAction(this.fetchContainersStats)
    await this.initializeZenohSession()
  },
  destroyed() {
    clearInterval(this.metrics_interval)
    this.stopUploadKeepAlive()
    if (this.zenoh_session) {
      this.zenoh_session.close()
      this.zenoh_session = null
    }
  },
  methods: {
    async initializeZenohSession() {
      if (this.zenoh_session) {
        return
      }
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const url = `${protocol}://${window.location.host}/zenoh-api/`
        const config = new Config(url)
        this.zenoh_session = await Session.open(config)
      } catch (error) {
        console.error('[ExtensionManagerView] Failed to connect to zenoh:', error)
      }
    },
    clearEditedExtension() {
      this.edited_extension = null
    },
    setInstallFromFilePhase(phase: TarInstallPhase) {
      this.install_from_file_phase = phase
      if (phase !== 'error') {
        this.install_from_file_error = null
        this.install_from_file_failed_step = null
        this.install_from_file_last_level = TAR_PHASE_LEVEL[phase]
      }
    },
    getTarStepStatus(stepKey: TarStepKey): TarStepStatus {
      if (this.install_from_file_phase === 'error' && this.install_from_file_failed_step === stepKey) {
        return 'error'
      }
      const currentLevel = this.install_from_file_phase === 'error'
        ? this.install_from_file_last_level
        : TAR_PHASE_LEVEL[this.install_from_file_phase]
      const stepIndex = TAR_STEP_ORDER.indexOf(stepKey)
      if (currentLevel > stepIndex) {
        return 'complete'
      }
      if (currentLevel === stepIndex && this.install_from_file_phase !== 'error') {
        return 'active'
      }
      return 'pending'
    },
    tarStepColor(status: TarStepStatus): string {
      switch (status) {
        case 'complete':
          return 'success'
        case 'error':
          return 'error'
        case 'active':
          return 'primary'
        default:
          return 'secondary'
      }
    },
    tarStepTextClass(status: TarStepStatus): string {
      switch (status) {
        case 'complete':
          return 'success--text'
        case 'error':
          return 'error--text'
        case 'active':
          return 'primary--text'
        default:
          return 'text--secondary'
      }
    },
    currentTarStepKey(): TarStepKey {
      return currentStepForPhase(this.install_from_file_phase)
    },
    applyInstallFromFileError(message: string) {
      this.install_from_file_error = message
      this.install_from_file_failed_step = this.currentTarStepKey()
      this.install_from_file_status_text = ''
      this.install_from_file_phase = 'error'
    },
    openInstallFromFileDialog(): void {
      this.fab_menu = false
      this.show_install_from_file_dialog = true
    },
    closeInstallFromFileDialog(): void {
      this.show_install_from_file_dialog = false
    },
    startUploadKeepAlive(): void {
      if (!this.upload_temp_tag) {
        return
      }

      this.stopUploadKeepAlive()
      this.upload_keep_alive_task = new OneMoreTime(
        { delay: 5 * 60 * 1000, autostart: false, disposeWith: this },
        () => this.sendUploadKeepAlive(),
      )
      this.upload_keep_alive_task.start()
    },
    stopUploadKeepAlive(): void {
      if (this.upload_keep_alive_task) {
        this.upload_keep_alive_task.stop()
        this.upload_keep_alive_task = null
      }
    },
    sendUploadKeepAlive(): Promise<void> | void {
      if (!this.upload_temp_tag) {
        return
      }
      kraken.keepTemporaryExtensionAlive(this.upload_temp_tag).catch((error) => {
        notifier.pushBackError('EXTENSION_UPLOAD_KEEP_ALIVE_FAIL', error)
      })
    },
    resetUploadFlow(options: { keepFile?: boolean } = {}) {
      if (!options.keepFile) {
        this.selected_tar_file = null
      }
      this.stopUploadKeepAlive()
      this.upload_temp_tag = null
      this.upload_metadata = null
      this.install_from_file_upload_progress = 0
      this.install_from_file_install_progress = 0
      this.install_from_file_status_text = ''
      this.install_from_file_error = null
      this.install_from_file_failed_step = null
      this.install_from_file_last_level = -1
      this.setInstallFromFilePhase('idle')
      this.file_uploading = false
    },
    onTarFileSelected(file: File | File[] | null) {
      const selected = Array.isArray(file) ? file[0] : file
      if (!selected) {
        this.resetUploadFlow()
        return
      }
      this.resetUploadFlow({ keepFile: true })
      this.selected_tar_file = selected
      this.setInstallFromFilePhase('selected')
    },
    handleFileUploadProgress(progressEvent: UploadProgressEvent) {
      if (!progressEvent.total || progressEvent.total <= 0) {
        this.setInstallFromFilePhase('uploading')
        return
      }
      const ratio = progressEvent.loaded / progressEvent.total
      const percent = Math.min(100, Math.round(ratio * 100))
      this.install_from_file_upload_progress = percent
      if (percent >= 100) {
        this.setInstallFromFilePhase('processing')
      } else if (this.install_from_file_phase !== 'uploading') {
        this.setInstallFromFilePhase('uploading')
      }
    },
    async uploadSelectedTarFile(): Promise<void> {
      if (!this.selected_tar_file || this.file_uploading) {
        return
      }
      this.install_from_file_upload_progress = 0
      this.setInstallFromFilePhase('uploading')
      this.file_uploading = true
      try {
        const response = await kraken.uploadExtensionTarFile(
          this.selected_tar_file,
          (progressEvent) => this.handleFileUploadProgress(progressEvent),
        )
        this.upload_temp_tag = response.temp_tag
        this.upload_metadata = response.metadata
        this.startUploadKeepAlive()
        this.setInstallFromFilePhase('ready')
      } catch (error) {
        this.applyInstallFromFileError(String(error))
        notifier.pushBackError('EXTENSION_UPLOAD_FAIL', error)
      } finally {
        this.file_uploading = false
      }
    },
    async update(extension: InstalledExtensionData, version: string) {
      this.show_pull_output = true
      const tracker = this.getTracker()
      kraken.updateExtensionToVersion(
        extension.identifier,
        version,
        (progressEvent) => this.handleDownloadProgress(progressEvent.event, tracker),
      )
        .then(() => {
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          this.alerter = true
          this.alerter_error = String(error)
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        })
        .finally(() => {
          this.resetPullOutput()
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

      const isUploadFlow = Boolean(this.upload_temp_tag)

      if (isUploadFlow) {
        // This is from a file upload, use finalize endpoint
        await this.finalizeUploadedExtension(this.edited_extension)
      } else {
        // This is a regular extension creation
        await this.install(this.edited_extension)
      }

      this.show_dialog = false
      this.edited_extension = null
      if (!isUploadFlow) {
        this.upload_metadata = null
      }
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
      try {
        this.running_containers = await kraken.listContainers()
      } catch (error) {
        notifier.pushBackError('RUNNING_CONTAINERS_FETCH_FAIL', error)
      }
    },
    async fetchContainersStats(): Promise<void> {
      kraken.getContainersStats()
        .then((response) => {
          this.metrics = response
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
      kraken.getInstalledExtensions()
        .then((response) => {
          this.installed_extensions = {}
          for (const extension of response) {
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
    showLogs(extension: InstalledExtensionData) {
      this.selected_log_extension_identifier = extension.identifier
      this.selected_log_extension_name = extension.name || extension.identifier
      this.show_log = true
    },
    showModal(extension: ExtensionData) {
      this.show_dialog = true
      this.selected_extension = extension
    },
    async install(extension: InstalledExtensionData) {
      this.show_dialog = false
      this.show_pull_output = true
      const tracker = this.getTracker()

      kraken.installExtension(
        extension,
        (progressEvent) => this.handleDownloadProgress(progressEvent.event, tracker),
      )
        .then(() => {
          this.fetchInstalledExtensions()
        })
        .catch((error) => {
          this.alerter = true
          this.alerter_error = String(error)
          notifier.pushBackError('EXTENSIONS_INSTALL_FAIL', error)
        })
        .finally(() => {
          this.resetPullOutput()
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
      await this.install({
        identifier: this.selected_extension?.identifier,
        name: this.selected_extension?.name,
        docker: this.selected_extension?.docker,
        tag,
        enabled: true,
        permissions: JSON.stringify(this.selected_extension?.versions[tag].permissions),
        user_permissions: permissions ?? '',
      })
    },
    async uninstall(extension: InstalledExtensionData) {
      this.setLoading(extension, true)
      kraken.uninstallExtension(extension.identifier)
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
      kraken.disableExtension(extension.identifier)
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
      kraken.enableExtension(extension.identifier, extension.tag)
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
      kraken.restartExtension(extension.identifier)
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
    getTracker(): PullTracker {
      return new PullTracker(
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
    },
    resetPullOutput() {
      this.show_pull_output = false
      this.show_dialog = false
      this.pull_output = ''
      this.download_percentage = 0
      this.extraction_percentage = 0
      this.status_text = ''
    },
    handleDownloadProgress(progressEvent: StreamProgressEvent, tracker: PullTracker) {
      tracker.digestNewData(progressEvent)
      this.pull_output = tracker.pull_output
      this.download_percentage = tracker.download_percentage
      this.extraction_percentage = tracker.extraction_percentage
      this.status_text = tracker.overall_status
      if (this.install_from_file_phase === 'installing') {
        const percent = Number.isFinite(tracker.download_percentage)
          ? Math.min(100, Math.max(0, Math.round(tracker.download_percentage)))
          : 0
        this.install_from_file_install_progress = percent
        if (tracker.overall_status) {
          this.install_from_file_status_text = tracker.overall_status
        }
      }
    },
    openCreationDialogFromUpload(metadata: ExtensionUploadMetadata | null = this.upload_metadata): void {
      if (!metadata) {
        return
      }
      const serializedPermissions = typeof metadata.permissions === 'string'
        ? metadata.permissions
        : JSON.stringify(metadata.permissions || {})

      this.edited_extension = {
        identifier: metadata.identifier || 'yourorganization.yourextension',
        name: metadata.name || '',
        docker: metadata.docker || '',
        tag: metadata.tag || 'latest',
        enabled: true,
        permissions: serializedPermissions,
        user_permissions: serializedPermissions,
        editing: false,
      }
    },
    async finalizeUploadedExtension(extension: InstalledExtensionData): Promise<void> {
      if (!this.upload_temp_tag) {
        return
      }

      this.show_pull_output = true
      const tracker = this.getTracker()
      this.setInstallFromFilePhase('installing')
      this.install_from_file_install_progress = 0
      this.install_from_file_status_text = 'Starting installation...'

      try {
        await kraken.finalizeExtension(
          extension,
          this.upload_temp_tag,
          (progressEvent) => this.handleDownloadProgress(progressEvent.event, tracker),
        )
        this.setInstallFromFilePhase('success')
        this.install_from_file_status_text = 'Extension installed successfully'
        this.stopUploadKeepAlive()
        this.upload_temp_tag = null
        this.upload_metadata = null
        this.fetchInstalledExtensions()
      } catch (error) {
        this.applyInstallFromFileError(String(error))
        this.alerter = true
        this.alerter_error = String(error)
        notifier.pushBackError('EXTENSION_FINALIZE_FAIL', error)
      } finally {
        this.resetPullOutput()
      }
    },
  },
})
</script>

<style>
.main-container {
  background-color: var(--v-sheet_bg-base) !important;
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
  padding: 0 !important;
}

pre.logs {
  color: var(--v-sheet_bg-base);
  background: var(--v-sheet_bg_complement-base);
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

.tar-upload-card {
  background-color: var(--v-sheet_bg-base) !important;
}

.tar-upload-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.upload-phase-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-phase {
  border-radius: 12px;
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  padding: 12px 16px;
  background-color: var(--v-sheet_bg-base);
  transition: border-color 0.2s ease;
}

.upload-phase.active {
  border-color: var(--v-primary-base);
}

.upload-phase.complete {
  border-color: var(--v-success-base);
}

.upload-phase.error {
  border-color: var(--v-error-base);
}

.upload-phase__header {
  display: flex;
  align-items: flex-start;
}

.upload-phase__title {
  font-weight: 600;
}

.metadata-preview {
  border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
  border-radius: 8px;
  padding: 12px 16px;
  background-color: var(--v-sheet_bg-base);
}

.metadata-preview__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px 24px;
}
</style>
