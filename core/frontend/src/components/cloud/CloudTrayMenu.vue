<template>
  <v-menu
    v-if="is_tray_visible"
    v-model="menu_opened"
    :close-on-content-click="false"
    nudge-left="370"
    nudge-bottom="25"
  >
    <template
      #activator="{ on, attrs }"
    >
      <v-badge
        :value="pendingCount > 0"
        :content="pendingBadgeLabel"
        color="error"
        overlap
      >
        <v-card
          id="cloud-tray-menu-button"
          elevation="0"
          color="transparent"
          v-bind="attrs"
          v-on="on"
        >
          <v-icon
            v-tooltip="'Cloud sync status'"
            class="px-1"
            color="white"
          >
            mdi-cloud
          </v-icon>
        </v-card>
      </v-badge>
    </template>
    <v-card
      elevation="1"
      width="370"
      min-height="300"
      max-height="50vh"
    >
      <v-container
        v-if="operation_in_progress"
        class="text-center fill-height d-flex flex-column justify-center align-center"
        style="height: 300px;"
      >
        <spinning-logo
          size="30%"
          :subtitle="operation_description"
        />
        <pull-progress
          :progress="pull_tracker?.pull_output ?? ''"
          :show="pull_show_modal"
          :download="pull_tracker?.download_percentage ?? 0"
          :extraction="pull_tracker?.extraction_percentage ?? 0"
          :statustext="pull_tracker?.overall_status ?? ''"
        />
      </v-container>
      <v-container
        v-else-if="operation_error_message"
        class="text-center fill-height d-flex flex-column justify-center align-center"
        style="height: 300px;"
      >
        <v-icon
          color="red"
          size="70"
        >
          mdi-alert-octagon
        </v-icon>
        <v-card-title>
          {{ operation_error_title }}
        </v-card-title>
        <v-card-subtitle class="pt-2">
          {{ operation_error_message }}
        </v-card-subtitle>
      </v-container>
      <v-container
        v-else-if="is_major_tom_installed"
        class="py-0 px-0"
      >
        <v-app-bar
          elevate-on-scroll
        >
          <v-toolbar-title>Cloud</v-toolbar-title>
          <v-spacer v-if="is_cloud_setup_complete" />
          <span
            v-if="is_cloud_setup_complete"
            class="text-caption text--secondary"
          >
            {{ statusSummary }}
          </span>
        </v-app-bar>

        <v-container class="px-0 py-0">
          <template v-if="is_cloud_setup_complete">
            <v-tabs
              v-model="active_tab"
              grow
              background-color="transparent"
              class="cloud-tray-tabs"
            >
              <v-tab>Account</v-tab>
              <v-tab>Uploads</v-tab>
            </v-tabs>
            <v-tabs-items v-model="active_tab">
              <v-tab-item>
                <cloud-settings-tab
                  :is-token-set="is_token_set"
                  :setting-token="setting_token"
                  :token="token"
                  :blueos-cloud-url="blueos_cloud_url"
                  :blueos-cloud-vehicles-url="blueos_cloud_vehicles_url"
                  @toggle-token-input="setting_token = $event"
                  @update:token="token = $event"
                  @submit-token="setMajorTomToken"
                />
              </v-tab-item>
              <v-tab-item>
                <cloud-sync-status-tab
                  :summary-message="statusSummary"
                  :items="cloud_sync_items"
                  :active-count="activeCount"
                  :pending-count="pendingCount"
                  :get-file-name="getFileName"
                  :format-file-size="formatFileSize"
                  :format-upload-progress="formatUploadProgress"
                  :missions-url="missions_url"
                />
              </v-tab-item>
            </v-tabs-items>
          </template>
          <template v-else>
            <cloud-settings-tab
              :is-token-set="is_token_set"
              :setting-token="setting_token"
              :token="token"
              :blueos-cloud-url="blueos_cloud_url"
              :blueos-cloud-vehicles-url="blueos_cloud_vehicles_url"
              @toggle-token-input="setting_token = $event"
              @update:token="token = $event"
              @submit-token="setMajorTomToken"
            />
          </template>
        </v-container>
      </v-container>
      <v-container
        v-else
        class="text-center fill-height d-flex flex-column justify-center align-center"
        style="height: 300px;"
      >
        <v-icon
          color="yellow"
          size="70"
        >
          mdi-link-off
        </v-icon>
        <v-card-title>
          Major Tom is not installed
        </v-card-title>
        <v-card-subtitle class="pt-2">
          To use the cloud features of the Ground Control you need to install it.
        </v-card-subtitle>
        <v-btn
          color="primary"
          elevation="3"
          class="mt-4"
          @click="installMajorTom"
        >
          Install Major Tom
        </v-btn>
      </v-container>
    </v-card>
  </v-menu>
</template>

<script lang="ts">
import {
  ChannelReceiver, Config, QueryTarget, Reply, ReplyError, Sample, Session, Subscriber,
} from '@eclipse-zenoh/zenoh-ts'
import axios from 'axios'
import { StatusCodes } from 'http-status-codes'
import Vue from 'vue'

import CloudSettingsTab from '@/components/cloud/CloudSettingsTab.vue'
import CloudSyncStatusTab from '@/components/cloud/CloudSyncStatusTab.vue'
import {
  CloudSyncDisplayItem,
  FileSyncEntry,
  FileSyncUploadingEvent,
  UploadingTransfer,
} from '@/components/cloud/types'
import SpinningLogo from '@/components/common/SpinningLogo.vue'
import PullProgress from '@/components/utils/PullProgress.vue'
import filebrowser from '@/libs/filebrowser'
import bag from '@/store/bag'
import { FilebrowserFile } from '@/types/filebrowser'
import { InstalledExtensionData, RunningContainer } from '@/types/kraken'
import back_axios from '@/utils/api'
import { prettifySize } from '@/utils/helper_functions'
import PullTracker from '@/utils/pull_tracker'

const KRAKEN_API_URL = '/kraken/v1.0'

const MAJOR_TOM_CLOUD_URL = 'https://blueos.cloud/major_tom/install'

const MAJOR_TOM_EXTENSION_IDENTIFIER = 'blueos.major_tom'

const BLUEOS_CLOUD_URL = 'https://app.blueos.cloud'

const BLUEOS_CLOUD_JOIN_URL = `${BLUEOS_CLOUD_URL}/api/agent/join/`

const BLUEOS_CLOUD_VEHICLES_URL = `${BLUEOS_CLOUD_URL}/vehicle/register/`

const MISSIONS_URL = `${BLUEOS_CLOUD_URL}/mission/`

const MAJOR_TOM_CLOUD_TOKEN_FILE = {
  path: 'system_root/root/.majortom/token.key',
  name: 'token.key',
  extension: 'key',
} as FilebrowserFile

const MAJOR_TOM_FILE_SYNC_PENDING_TOPIC = 'services/major_tom/file_sync/pending'
const MAJOR_TOM_FILE_SYNC_COMPLETED_TOPIC = 'services/major_tom/file_sync/completed'
const MAJOR_TOM_FILE_SYNC_UPLOADING_TOPIC = 'services/major_tom/file_sync/uploading'

export default Vue.extend({
  name: 'CloudTrayMenu',
  components: {
    CloudSyncStatusTab,
    CloudSettingsTab,
    SpinningLogo,
    PullProgress,
  },
  data() {
    return {
      token: '',
      local_token: '',
      setting_token: false,
      menu_opened: false,
      active_tab: 0,
      operation_in_progress: false,
      operation_description: '',
      pull_tracker: null as PullTracker | null,
      pull_show_modal: false,
      operation_error_title: null as string | null,
      operation_error_message: null as string | null,
      installed_extensions: {} as Record<string, InstalledExtensionData>,
      running_containers: [] as RunningContainer[],
      once_opened: false,
      file_sync_session: null as Session | null,
      file_sync_session_promise: null as Promise<Session> | null,
      uploading_subscriber: null as Subscriber | null,
      cloud_pending_uploads: [] as FileSyncEntry[],
      cloud_completed_uploads: [] as FileSyncEntry[],
      cloud_uploading_transfers: {} as Record<string, UploadingTransfer>,
      file_sync_refresh_timeout: null as number | null,
      uploading_idle_timeout: null as number | null,
      file_sync_teardown_in_progress: null as Promise<void> | null,
    }
  },
  computed: {
    is_major_tom_installed(): boolean {
      return MAJOR_TOM_EXTENSION_IDENTIFIER in this.installed_extensions
    },
    is_major_tom_running(): boolean {
      const extension = this.installed_extensions[MAJOR_TOM_EXTENSION_IDENTIFIER]

      return this.running_containers.some(
        (container) => container.image === `${extension?.docker}:${extension?.tag}`,
      )
    },
    is_token_set(): boolean {
      return this.local_token !== ''
    },
    blueos_cloud_url(): string {
      return BLUEOS_CLOUD_URL
    },
    blueos_cloud_vehicles_url(): string {
      return BLUEOS_CLOUD_VEHICLES_URL
    },
    missions_url(): string {
      return MISSIONS_URL
    },
    is_major_tom_ready(): boolean {
      return this.is_major_tom_installed && this.is_major_tom_running
    },
    is_tray_visible(): boolean {
      return this.is_major_tom_ready || this.once_opened
    },
    is_cloud_setup_complete(): boolean {
      return this.is_token_set
    },
    cloud_active_uploads(): UploadingTransfer[] {
      return Object.values(this.cloud_uploading_transfers)
        .sort((a, b) => b.timestamp - a.timestamp)
    },
    cloud_pending_queue(): FileSyncEntry[] {
      return [...this.cloud_pending_uploads]
    },
    cloud_recent_completed(): FileSyncEntry[] {
      return [...this.cloud_completed_uploads].slice(-5).reverse()
    },
    activeCount(): number {
      return this.cloud_active_uploads.length
    },
    pendingCount(): number {
      return this.cloud_pending_queue.length
    },
    statusSummary(): string {
      if (this.activeCount > 0) {
        const noun = this.activeCount === 1 ? 'file' : 'files'
        return `Uploading ${this.activeCount} ${noun}`
      }
      if (this.pendingCount > 0) {
        const noun = this.pendingCount === 1 ? 'file pending' : 'files pending'
        return `${this.pendingCount} ${noun}`
      }
      return 'All caught up'
    },
    pendingBadgeLabel(): string {
      if (this.pendingCount <= 0) {
        return ''
      }
      return this.pendingCount > 99 ? '99+' : String(this.pendingCount)
    },
    cloud_sync_items(): CloudSyncDisplayItem[] {
      const uploadingItems: CloudSyncDisplayItem[] = this.cloud_active_uploads.map(
        (transfer) => ({
          id: `uploading-${transfer.file}`,
          path: transfer.file,
          display_path: transfer.display_path,
          size: transfer.total,
          status: 'uploading',
          sent: transfer.sent,
          total: transfer.total,
          progress: transfer.progress,
        }),
      )
      const pendingItems: CloudSyncDisplayItem[] = this.cloud_pending_queue.map(
        (entry, index) => ({
          id: `pending-${entry.path}-${index}`,
          path: entry.path,
          size: entry.size,
          status: 'pending',
        }),
      )
      const completedItems: CloudSyncDisplayItem[] = this.cloud_recent_completed.map(
        (entry, index) => ({
          id: `completed-${entry.path}-${index}`,
          path: entry.path,
          size: entry.size,
          status: 'completed',
        }),
      )

      return [...uploadingItems, ...pendingItems, ...completedItems]
    },
  },
  watch: {
    async menu_opened(new_value: boolean) {
      if (new_value) {
        this.once_opened = true
        await this.setUpTrayMenu()
        await this.initializeFileSyncTracking()
      } else {
        this.active_tab = 0
        setTimeout(() => {
          this.setting_token = false
          this.token = ''
        }, 200)
      }
    },
    async is_major_tom_ready(new_value: boolean) {
      if (new_value) {
        await this.initializeFileSyncTracking()
      } else {
        await this.teardownFileSyncTracking()
      }
    },
  },
  async mounted() {
    await this.setUpTrayMenu()
    await this.initializeFileSyncTracking()
  },
  async beforeDestroy() {
    await this.teardownFileSyncTracking()
  },
  methods: {
    async setUpTrayMenu() {
      await this.fetchExtensions()
      await this.fetchMajorTomToken()

      if (!this.once_opened && !this.is_major_tom_ready) {
        setTimeout(() => {
          this.setUpTrayMenu()
        }, 5000)
      }
    },
    async initializeFileSyncTracking(): Promise<void> {
      if (!this.is_major_tom_ready) {
        return
      }

      if (this.file_sync_teardown_in_progress) {
        try {
          await this.file_sync_teardown_in_progress
        } catch {
          // Teardown errors are already logged in teardown handler.
        }
      }
      const sessionReady = await this.ensureFileSyncSession()
      if (!sessionReady) {
        return
      }

      await this.fetchFileSyncQueues()
      await this.ensureUploadingSubscriber()
    },
    async ensureFileSyncSession(): Promise<boolean> {
      if (this.file_sync_session) {
        return true
      }

      if (this.file_sync_session_promise) {
        try {
          await this.file_sync_session_promise
          return this.file_sync_session !== null
        } catch {
          return false
        }
      }

      try {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const url = `${protocol}://${window.location.host}/zenoh-api/`
        const config = new Config(url)
        const sessionPromise = Session.open(config)
        this.file_sync_session_promise = sessionPromise
        this.file_sync_session = await sessionPromise
        return true
      } catch (error) {
        console.error('[CloudTrayMenu] Failed to open Zenoh session for file sync tracking:', error)
        return false
      } finally {
        this.file_sync_session_promise = null
      }
    },
    async fetchFileSyncQueues(): Promise<void> {
      try {
        const [pending, completed] = await Promise.all([
          this.queryFileSyncTopic(MAJOR_TOM_FILE_SYNC_PENDING_TOPIC),
          this.queryFileSyncTopic(MAJOR_TOM_FILE_SYNC_COMPLETED_TOPIC),
        ])

        this.cloud_pending_uploads = pending ?? []
        this.cloud_completed_uploads = completed ?? []
      } catch (error) {
        console.error('[CloudTrayMenu] Failed to fetch file sync queues:', error)
      }
    },
    async queryFileSyncTopic(topic: string): Promise<FileSyncEntry[] | null> {
      if (!this.file_sync_session) {
        return null
      }

      try {
        const receiver: ChannelReceiver<Reply> | undefined = await this.file_sync_session.get(topic, {
          target: QueryTarget.BEST_MATCHING,
        })

        if (!receiver) {
          console.warn(`[CloudTrayMenu] Query for ${topic} returned void receiver.`)
          return null
        }

        for await (const reply of receiver) {
          const response = reply.result()
          if (response instanceof Sample) {
            const payload = response.payload().toString()
            return this.parseFileSyncQueue(payload)
          }
          const errorResponse: ReplyError = response
          console.warn(`[CloudTrayMenu] Query error for ${topic}:`, errorResponse.payload().toString())
        }
      } catch (error) {
        console.error(`[CloudTrayMenu] Failed to query ${topic}:`, error)
      }

      return null
    },
    parseFileSyncQueue(payload: string): FileSyncEntry[] {
      try {
        const parsed = JSON.parse(payload)
        if (!Array.isArray(parsed)) {
          return []
        }

        const entries: FileSyncEntry[] = []
        for (const item of parsed) {
          if (Array.isArray(item) && item.length >= 2 && typeof item[0] === 'string') {
            const [path, rawSize] = item
            const size = typeof rawSize === 'number' ? rawSize : Number(rawSize) || 0
            entries.push({ path, size })
          } else if (item && typeof item === 'object') {
            const objectEntry = item as { file?: unknown; path?: unknown; size?: unknown }
            let candidatePath: string | undefined
            if (typeof objectEntry.file === 'string') {
              candidatePath = objectEntry.file
            } else if (typeof objectEntry.path === 'string') {
              candidatePath = objectEntry.path
            }
            if (candidatePath) {
              const size = typeof objectEntry.size === 'number' ? objectEntry.size : Number(objectEntry.size) || 0
              entries.push({ path: candidatePath, size })
            }
          }
        }

        return entries
      } catch (error) {
        console.error('[CloudTrayMenu] Failed to parse file sync payload:', error)
        return []
      }
    },
    async ensureUploadingSubscriber(): Promise<void> {
      if (this.uploading_subscriber || !this.file_sync_session) {
        return
      }

      try {
        this.uploading_subscriber = await this.file_sync_session.declareSubscriber(
          MAJOR_TOM_FILE_SYNC_UPLOADING_TOPIC,
          {
            handler: (sample: Sample) => {
              this.handleUploadingSample(sample)
            },
            history: true,
          },
        )
      } catch (error) {
        console.error('[CloudTrayMenu] Failed to subscribe to file upload updates:', error)
      }
    },
    handleUploadingSample(sample: Sample): void {
      try {
        const payload = sample.payload().toString()
        const event = JSON.parse(payload) as FileSyncUploadingEvent
        const transfer = this.normalizeUploadingEvent(event)
        if (!transfer) {
          return
        }

        this.resetUploadingIdleWatchdog()

        if (!transfer.completed) {
          this.$set(this.cloud_uploading_transfers, transfer.file, transfer)
        } else {
          this.$delete(this.cloud_uploading_transfers, transfer.file)
        }

        this.removeFromPendingQueue(transfer.file)

        if (transfer.completed) {
          this.scheduleFileSyncRefresh()
        }
      } catch (error) {
        console.error('[CloudTrayMenu] Failed to process uploading sample:', error)
      }
    },
    normalizeUploadingEvent(event: FileSyncUploadingEvent): UploadingTransfer | null {
      const rawFile = typeof event.file === 'string' ? event.file : null
      if (!rawFile) {
        return null
      }

      function toNumber(value: unknown): number {
        if (typeof value === 'number' && Number.isFinite(value)) {
          return value
        }
        const parsed = Number(value)
        return Number.isFinite(parsed) ? parsed : 0
      }

      const normalizedFile = this.normalizeFilePath(rawFile)
      const sent = toNumber(event.sent)
      const total = toNumber(event.total)
      const timestamp = toNumber(event.timestamp) || Date.now() / 1000
      const progress = total > 0 ? Math.min(Math.max(sent / total, 0), 1) : 0

      return {
        file: normalizedFile,
        display_path: rawFile,
        sent,
        total,
        timestamp,
        progress,
        completed: total > 0 && sent >= total,
      }
    },
    async teardownFileSyncTracking(): Promise<void> {
      if (this.file_sync_teardown_in_progress) {
        try {
          await this.file_sync_teardown_in_progress
        } catch {
          // Errors already handled in teardown promise.
        }
        return
      }

      const teardownPromise = (async () => {
        this.clearScheduledFileSyncRefresh()
        this.clearUploadingIdleWatchdog()

        try {
          if (this.uploading_subscriber) {
            await this.uploading_subscriber.undeclare()
          }
        } catch (error) {
          console.warn('[CloudTrayMenu] Failed to undeclare uploading subscriber:', error)
        } finally {
          this.uploading_subscriber = null
        }

        try {
          if (this.file_sync_session) {
            await this.file_sync_session.close()
          }
        } catch (error) {
          console.warn('[CloudTrayMenu] Failed to close file sync session:', error)
        } finally {
          this.file_sync_session = null
          this.file_sync_session_promise = null
        }

        this.cloud_pending_uploads = []
        this.cloud_completed_uploads = []
        this.cloud_uploading_transfers = {}
      })()

      this.file_sync_teardown_in_progress = teardownPromise

      try {
        await teardownPromise
      } finally {
        this.file_sync_teardown_in_progress = null
      }
    },
    normalizeFilePath(path: string): string {
      if (!path) {
        return ''
      }
      if (path.startsWith('/host/')) {
        return path.substring(5)
      }
      if (path === '/host') {
        return '/'
      }
      return path
    },
    pathsReferSameFile(pathA: string, pathB: string): boolean {
      return this.normalizeFilePath(pathA) === this.normalizeFilePath(pathB)
    },
    removeFromPendingQueue(canonicalPath: string): void {
      if (!canonicalPath) {
        return
      }
      this.cloud_pending_uploads = this.cloud_pending_uploads.filter(
        (entry) => !this.pathsReferSameFile(entry.path, canonicalPath),
      )
    },
    scheduleFileSyncRefresh(delay = 1500): void {
      this.clearScheduledFileSyncRefresh()
      this.file_sync_refresh_timeout = window.setTimeout(async () => {
        this.file_sync_refresh_timeout = null
        await this.fetchFileSyncQueues()
      }, delay)
    },
    clearScheduledFileSyncRefresh(): void {
      if (this.file_sync_refresh_timeout !== null) {
        clearTimeout(this.file_sync_refresh_timeout)
        this.file_sync_refresh_timeout = null
      }
    },
    resetUploadingIdleWatchdog(timeoutSeconds = 60): void {
      this.clearUploadingIdleWatchdog()
      this.uploading_idle_timeout = window.setTimeout(() => {
        this.uploading_idle_timeout = null
        this.fetchFileSyncQueues()
      }, timeoutSeconds * 1000)
    },
    clearUploadingIdleWatchdog(): void {
      if (this.uploading_idle_timeout !== null) {
        clearTimeout(this.uploading_idle_timeout)
        this.uploading_idle_timeout = null
      }
    },
    getFileName(path: string): string {
      if (!path) {
        return ''
      }
      const parts = path.split(/[/\\]/)
      return parts[parts.length - 1] || path
    },
    formatFileSize(value: number): string {
      if (!Number.isFinite(value)) {
        return 'N/A'
      }
      const size_kb = Math.max(value, 0) / 1024
      return prettifySize(size_kb)
    },
    formatUploadProgress(progress: number): string {
      if (!Number.isFinite(progress)) {
        return '0%'
      }
      return `${Math.round(progress * 100)}%`
    },
    startOperation(message: string): void {
      this.operation_description = message
      this.operation_error_title = null
      this.operation_error_message = null
      this.pull_show_modal = false
      this.operation_in_progress = true
    },
    setOperationError(title: string, error: unknown): void {
      this.operation_error_title = title
      this.operation_error_message = String(error)
    },
    async cleanMajorTomBagToken(): Promise<void> {
      const data = await bag.getData('major_tom')
      if (data && data.token) {
        delete data.token
      }
      await bag.setData('major_tom', { ...data })
    },
    async cleanMajorTomFileToken(): Promise<void> {
      await filebrowser.deleteFile(MAJOR_TOM_CLOUD_TOKEN_FILE)
    },
    async fetchMajorTomData(): Promise<InstalledExtensionData> {
      const data = await axios.get(MAJOR_TOM_CLOUD_URL)

      return data.data as InstalledExtensionData
    },
    async fetchMajorTomFileToken(): Promise<string | undefined> {
      try {
        const response = await fetch(await filebrowser.singleFileRelativeURL(MAJOR_TOM_CLOUD_TOKEN_FILE))
        return response.ok ? await response.text() : undefined
      } catch {
        return undefined
      }
    },
    async fetchMajorTomBagToken(): Promise<string | undefined> {
      const tomData = await bag.getData('major_tom')
      return tomData?.token ? String(tomData?.token) : undefined
    },
    async fetchMajorTomToken(): Promise<void> {
      const fileToken = await this.fetchMajorTomFileToken()
      let tokenToUse = fileToken
      if (tokenToUse === undefined) {
        tokenToUse = await this.fetchMajorTomBagToken()
      }

      if (!await this.isMajorTomTokenValid(tokenToUse, true)) {
        /** We do not remove the token since it may be used in other parts as a developer token */
        tokenToUse = undefined
      } else if (tokenToUse !== undefined && tokenToUse !== fileToken) {
        /** Copy bag token to file token, migrating to new token system */
        await this.updateMajorTomToken(tokenToUse)
      }

      this.local_token = tokenToUse ?? ''
    },
    async updateMajorTomBagToken(token: string): Promise<void> {
      await this.cleanMajorTomBagToken()

      const tomData = await bag.getData('major_tom')
      await bag.setData('major_tom', { ...tomData, token })
    },
    async updateMajorTomFileToken(token: string): Promise<void> {
      try {
        await this.cleanMajorTomFileToken()
      } catch {
        /** When updating the token, the file may not exist so we can ignore the error */
      }

      await filebrowser.createFile(MAJOR_TOM_CLOUD_TOKEN_FILE.path, true)
      await filebrowser.writeToFile(MAJOR_TOM_CLOUD_TOKEN_FILE.path, token)
    },
    async updateMajorTomToken(token: string): Promise<void> {
      await this.updateMajorTomBagToken(token)
      await this.updateMajorTomFileToken(token)
    },
    async fetchExtensions(): Promise<void> {
      if (this.operation_in_progress) {
        return
      }
      this.startOperation('Checking if Major Tom is installed...')

      try {
        const installed = await back_axios({
          method: 'get',
          url: `${KRAKEN_API_URL}/installed_extensions`,
          timeout: 10000,
        })
        this.installed_extensions = {}
        for (const extension of installed.data) {
          this.installed_extensions[extension.identifier] = extension
        }

        const running = await back_axios({
          method: 'get',
          url: `${KRAKEN_API_URL}/list_containers`,
          timeout: 10000,
        })
        this.running_containers = running.data
      } catch (error) {
        this.setOperationError('Failed to determine if Major Tom is installed.', error)
      }

      this.operation_in_progress = false
    },
    async installMajorTom(): Promise<void> {
      if (this.operation_in_progress) {
        return
      }
      this.startOperation('Installing Major Tom...')

      this.pull_tracker = new PullTracker(
        () => console.log('Major Tom Install Ready'),
        (error: string) => {
          this.setOperationError('Failed to install Major Tom.', error)
        },
      )

      try {
        const majorTomData = await this.fetchMajorTomData()

        this.pull_show_modal = true

        await back_axios({
          method: 'POST',
          url: `${KRAKEN_API_URL}/extension/install`,
          data: majorTomData,
          onDownloadProgress: (progressEvent) => {
            this.pull_tracker?.digestNewData(progressEvent.event)
          },
        })
      } catch (error) {
        this.setOperationError('Failed to install Major Tom.', error)
      }

      this.operation_in_progress = false
      this.pull_show_modal = false

      await this.fetchExtensions()
    },
    async isMajorTomTokenValid(token: string | undefined, ignoreOfflineError = false): Promise<boolean> {
      if (token === undefined) {
        return false
      }

      try {
        await axios.put(
          BLUEOS_CLOUD_JOIN_URL,
          {},
          {
            headers: {
              Authorization: `Token ${token}`,
            },
          },
        )
      } catch (error: unknown) {
        if (axios.isAxiosError(error) && error.response) {
          return error.response.status === StatusCodes.BAD_REQUEST
        }
        return ignoreOfflineError
      }
      return false
    },
    async setMajorTomToken() {
      if (this.operation_in_progress) {
        return
      }
      this.startOperation('Setting Major Tom token...')

      const isTokenValid = await this.isMajorTomTokenValid(this.token)

      if (isTokenValid) {
        try {
          await this.updateMajorTomToken(this.token)

          await back_axios({
            url: `${KRAKEN_API_URL}/extension/restart`,
            method: 'POST',
            params: {
              extension_identifier: MAJOR_TOM_EXTENSION_IDENTIFIER,
            },
            timeout: 10000,
          })
        } catch (restart_error) {
          this.setOperationError('Failed to set Major Tom token.', restart_error)
        }
      } else {
        this.setOperationError(
          'Failed to set Major Tom token.',
          'Invalid token. Please try again with a valid token.',
        )
      }

      this.operation_in_progress = false
      this.pull_show_modal = false

      this.token = ''
      this.setting_token = false

      await this.fetchMajorTomToken()
    },
  },
})
</script>

<style scoped>
.cloud-tray-tabs {
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
</style>
