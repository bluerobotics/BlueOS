<template>
  <v-container fluid class="records-view">
    <v-overlay
      v-if="!isSafe"
      absolute
      :opacity="0.9"
      z-index="10"
    >
      <div class="d-flex flex-column align-center text-center pa-4">
        <v-icon large color="warning" class="mb-3">
          mdi-alert-outline
        </v-icon>
        <p class="mb-0">
          Recording browsing is paused while the vehicle is armed,
          so the link stays free for vehicle control.
        </p>
      </div>
    </v-overlay>

    <v-alert
      v-if="recordings.length > 0"
      type="warning"
      dense
      class="mb-4"
    >
      Playing or downloading a recording pulls it over the vehicle link and can take most of the
      available bandwidth, which may disturb vehicle operations. Close the player when you are done with it.
    </v-alert>

    <v-alert
      v-if="error"
      type="error"
      dense
      class="mb-4"
    >
      {{ error }}
    </v-alert>

    <v-alert
      v-else-if="!loading && recordings.length === 0"
      type="info"
      dense
      class="mb-4"
    >
      No recordings found yet.
    </v-alert>

    <v-alert
      v-if="pageBusy"
      type="warning"
      dense
      prominent
      class="mb-4"
    >
      <div class="d-flex align-center flex-wrap">
        <v-icon class="mr-2">
          mdi-open-in-app
        </v-icon>
        <div>
          Keep this page open until the current download or export finishes.
          Those steps run in this browser and will stop if you leave.
          Repair on the vehicle continues, but you would lose progress shown here.
        </div>
      </div>
    </v-alert>

    <v-sheet rounded class="d-flex align-center flex-wrap mb-4 px-2 pt-2 toolbar">
      <v-select
        v-if="dateFilterOptions.length > 1"
        v-model="selectedDate"
        :items="dateFilterOptions"
        label="Filter by date (UTC)"
        dense
        outlined
        hide-details
        class="date-filter mr-3 mb-2"
      />
      <v-checkbox
        v-if="filteredRecordings.length > 0"
        :input-value="allFilteredSelected"
        :indeterminate="someFilteredSelected && !allFilteredSelected"
        dense
        hide-details
        class="mt-0 pt-0 mr-3 mb-2"
        label="Select all"
        @change="toggleSelectAllFiltered"
      />
      <v-spacer />
      <v-btn
        v-tooltip="'Cards'"
        icon
        small
        class="mb-2"
        :color="layout === 'cards' ? 'primary' : undefined"
        @click="layout = 'cards'"
      >
        <v-icon small>
          mdi-view-grid-outline
        </v-icon>
      </v-btn>
      <v-btn
        v-tooltip="'Table'"
        icon
        small
        class="mb-2"
        :color="layout === 'table' ? 'primary' : undefined"
        @click="layout = 'table'"
      >
        <v-icon small>
          mdi-view-list-outline
        </v-icon>
      </v-btn>
    </v-sheet>

    <v-sheet
      v-if="selectedFiles.length > 0"
      rounded
      class="d-flex align-center flex-wrap mb-4 pa-3"
    >
      <div class="mr-4 mb-2">
        <div class="subtitle-2">
          {{ selectedFiles.length }} selected
        </div>
        <div class="caption grey--text text--darken-1">
          {{ selectionStats }}
        </div>
      </div>
      <v-spacer />
      <v-btn
        v-tooltip="canDownloadSelected ? 'Download the selected recordings' : 'Nothing selected can be downloaded'"
        small
        outlined
        color="primary"
        class="mr-2 mb-2"
        :disabled="!canDownloadSelected || pageBusy"
        :loading="bulkDownloading"
        @click="downloadSelected"
      >
        <v-icon small left>
          mdi-download
        </v-icon>
        Download
      </v-btn>
      <v-btn
        v-tooltip="canRepairSelected
          ? 'Rewrite selected recordings so they can be read'
          : 'Nothing selected needs repair'"
        small
        outlined
        color="primary"
        class="mr-2 mb-2"
        :disabled="!canRepairSelected || pageBusy"
        :loading="bulkRepairing"
        @click="askRepair(selectedFiles)"
      >
        <v-icon small left>
          mdi-wrench
        </v-icon>
        Repair
      </v-btn>
      <v-btn
        v-tooltip="canDeleteSelected ? 'Delete the selected recordings' : 'Nothing selected can be deleted'"
        small
        outlined
        color="error"
        class="mr-2 mb-2"
        :disabled="!canDeleteSelected || pageBusy"
        @click="askDelete(selectedFiles)"
      >
        <v-icon small left>
          mdi-delete
        </v-icon>
        Delete
      </v-btn>
      <v-btn
        small
        text
        class="mb-2"
        @click="clearSelection"
      >
        Clear
      </v-btn>
    </v-sheet>

    <v-row v-if="layout === 'cards'">
      <v-col
        v-for="file in filteredRecordings"
        :key="file.path"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <div class="record-card-wrap">
          <v-checkbox
            :input-value="isSelected(file)"
            dense
            hide-details
            class="card-select"
            @click.stop
            @change="toggleSelected(file)"
          />
          <v-card outlined class="record-card d-flex flex-column">
            <div class="preview-wrapper">
              <div
                class="record-preview grey darken-3 d-flex flex-column align-center justify-center"
                :class="{ 'preview-clickable': canPlay(file) }"
                :role="canPlay(file) ? 'button' : undefined"
                :tabindex="canPlay(file) ? 0 : undefined"
                @click="canPlay(file) && openPlayer(file)"
                @keydown.enter="canPlay(file) && openPlayer(file)"
              >
                <img
                  v-if="thumbnailUrl(file)"
                  :src="thumbnailUrl(file)"
                  class="preview-image"
                  alt=""
                >
                <div class="preview-overlay d-flex flex-column align-center justify-center">
                  <v-btn
                    v-if="canPlay(file)"
                    icon
                    large
                    color="primary"
                    class="play-btn"
                  >
                    <v-icon large>
                      mdi-play-circle
                    </v-icon>
                  </v-btn>
                  <v-progress-circular
                    v-else-if="file.state === 'repairing'"
                    :indeterminate="!repairProgress[file.path]"
                    :value="repairProgress[file.path]?.percent ?? 0"
                    color="primary"
                    size="48"
                  >
                    <span v-if="repairProgress[file.path]" class="caption">
                      {{ Math.round(repairProgress[file.path].percent) }}%
                    </span>
                  </v-progress-circular>
                  <div class="mt-2 caption text-center preview-caption">
                    <div v-if="durationLabel(file)">
                      {{ durationLabel(file) }}
                    </div>
                    <div v-if="file.state === 'recording'">
                      recording…
                    </div>
                    <div v-else-if="endedLabel(file)">
                      ended {{ endedLabel(file) }}
                    </div>
                    <template v-if="file.state === 'needs_repair'">
                      <div>{{ repairFailure(file) ?? 'Recording index is missing' }}</div>
                      <v-btn
                        v-tooltip="'Rewrite this recording on the vehicle so that it can be read'"
                        x-small
                        text
                        color="primary"
                        class="mt-1"
                        :disabled="!canRepair(file)"
                        @click.stop="askRepair([file])"
                      >
                        <v-icon x-small left>
                          mdi-wrench
                        </v-icon>
                        Repair
                      </v-btn>
                    </template>
                    <div v-else-if="file.state === 'repairing'">
                      <div>Repairing recording index…</div>
                      <div v-if="repairProgress[file.path]">
                        {{ repairProgress[file.path].label }}
                      </div>
                      <v-btn
                        v-tooltip="'Stop the rewrite and leave the recording as it is'"
                        x-small
                        text
                        color="primary"
                        class="mt-1"
                        @click.stop="cancelRepair(file)"
                      >
                        <v-icon x-small left>
                          mdi-stop
                        </v-icon>
                        Stop
                      </v-btn>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <v-card-title class="py-2">
              <div class="text-truncate">
                {{ recordingTitle(file) }}
              </div>
            </v-card-title>
            <v-card-subtitle class="py-0">
              <v-chip
                x-small
                class="mr-2"
                :color="stateChipColor(file.state)"
              >
                {{ stateChipLabel(file) }}
              </v-chip>
              <span class="mr-2">{{ formatSize(file.size_bytes) }}</span>
              <span class="caption">{{ formatDate(file.created) }}</span>
            </v-card-subtitle>
            <v-card-subtitle v-if="tracksLabel(file)" class="py-0 caption">
              {{ tracksLabel(file) }}
            </v-card-subtitle>
            <v-spacer />
            <v-card-actions class="pt-0">
              <span v-tooltip="deleteTooltip(file)">
                <v-btn
                  icon
                  small
                  color="error"
                  :disabled="!canDelete(file)"
                  @click="askDelete([file])"
                >
                  <v-icon>mdi-delete</v-icon>
                </v-btn>
              </span>
              <v-btn
                v-if="file.state === 'needs_repair'"
                v-tooltip="'Rewrite this recording on the vehicle so that it can be read'"
                icon
                small
                color="primary"
                :disabled="!canRepair(file)"
                @click="repair(file)"
              >
                <v-icon>mdi-wrench</v-icon>
              </v-btn>
              <v-spacer />
              <span v-tooltip="downloadTooltip(file)">
                <v-btn
                  icon
                  small
                  color="primary"
                  :disabled="!canDownload(file)"
                  @click="downloadRecording(file)"
                >
                  <v-icon>mdi-download</v-icon>
                </v-btn>
              </span>
            </v-card-actions>
          </v-card>
        </div>
      </v-col>
    </v-row>

    <v-card
      v-else
      elevation="1"
    >
      <v-card-text>
        <v-data-table
          v-model="selectedTableItems"
          :headers="tableHeaders"
          :items="tableItems"
          :items-per-page="10"
          :footer-props="{ 'items-per-page-options': [10, 25, 50, -1] }"
          :mobile-breakpoint="0"
          item-key="path"
          show-select
          :sort-by.sync="tableSortBy"
          :sort-desc.sync="tableSortDesc"
          class="records-table"
          @click:row="openPlayerFromRow"
        >
          <template #item.preview="{ item }">
            <div
              class="table-preview grey darken-3"
              :class="{ 'preview-clickable': canPlay(item.file) }"
            >
              <img
                v-if="thumbnailUrl(item.file)"
                :src="thumbnailUrl(item.file)"
                class="table-preview-image"
                alt=""
              >
            </div>
          </template>
          <template #item.name="{ item }">
            <div class="font-weight-medium">
              {{ recordingTitle(item.file) }}
            </div>
          </template>
          <template #item.state="{ item }">
            <v-chip
              x-small
              :color="stateChipColor(item.file.state)"
            >
              {{ stateChipLabel(item.file) }}
            </v-chip>
          </template>
          <template #item.size_bytes="{ item }">
            {{ formatSize(item.file.size_bytes) }}
          </template>
          <template #item.created="{ item }">
            {{ formatDate(item.file.created) }}
          </template>
          <template #item.duration="{ item }">
            {{ durationLabel(item.file) ?? '—' }}
          </template>
          <template #item.tracks="{ item }">
            {{ tracksLabel(item.file) ?? '—' }}
          </template>
          <template #item.actions="{ item }">
            <div class="d-flex align-center justify-end" @click.stop>
              <span v-tooltip="deleteTooltip(item.file)">
                <v-btn
                  icon
                  small
                  color="error"
                  :disabled="!canDelete(item.file)"
                  @click="askDelete([item.file])"
                >
                  <v-icon small>
                    mdi-delete
                  </v-icon>
                </v-btn>
              </span>
              <v-btn
                v-if="item.file.state === 'needs_repair'"
                v-tooltip="'Rewrite this recording on the vehicle so that it can be read'"
                icon
                small
                color="primary"
                :disabled="!canRepair(item.file)"
                @click="askRepair([item.file])"
              >
                <v-icon small>
                  mdi-wrench
                </v-icon>
              </v-btn>
              <v-btn
                v-if="item.file.state === 'repairing'"
                v-tooltip="'Stop the rewrite and leave the recording as it is'"
                icon
                small
                color="primary"
                @click="cancelRepair(item.file)"
              >
                <v-icon small>
                  mdi-stop
                </v-icon>
              </v-btn>
              <span v-tooltip="downloadTooltip(item.file)">
                <v-btn
                  icon
                  small
                  color="primary"
                  :disabled="!canDownload(item.file)"
                  @click="downloadRecording(item.file)"
                >
                  <v-icon small>
                    mdi-download
                  </v-icon>
                </v-btn>
              </span>
            </div>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>

    <v-dialog
      v-model="playerOpen"
      :fullscreen="$vuetify.breakpoint.smAndDown"
      :max-width="$vuetify.breakpoint.smAndDown ? undefined : 1080"
      scrollable
      :persistent="playerBusy"
      @click:outside="closePlayer"
    >
      <v-card class="player-card">
        <v-card-title class="headline d-flex align-center flex-wrap">
          <div class="text-truncate mr-2">
            {{ activeRecord ? recordingTitle(activeRecord) : '' }}
          </div>
          <span
            v-if="activeRecordMeta"
            class="caption grey--text text--darken-1 font-weight-regular mr-2"
          >
            {{ activeRecordMeta }}
          </span>
          <v-spacer />
          <v-btn
            v-if="activeRecord && canDownload(activeRecord)"
            v-tooltip="'Download the whole recording file. This is not cut to the export time range.'"
            small
            outlined
            color="primary"
            class="mr-2"
            :disabled="!canDownload(activeRecord)"
            @click="downloadRecording(activeRecord)"
          >
            <v-icon small left>
              mdi-download
            </v-icon>
            Download full MCAP
          </v-btn>
          <v-btn
            v-tooltip="'Close'"
            icon
            small
            class="ml-2"
            color="primary"
            :disabled="playerBusy"
            @click.stop="closePlayer"
          >
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text>
          <mcap-video-player
            v-if="activeRecord"
            :key="activeRecord.path"
            :url="activeRecord.stream_url"
            :index-url="activeRecord.index_url"
            :ongoing="activeRecord.state === 'recording'"
            @busy="onPlayerBusy"
            @summary="onPlayerSummary"
          />
        </v-card-text>
      </v-card>
    </v-dialog>

    <WarningDialog
      v-model="deleteDialog"
      :message="deleteMessage"
      confirm-label="Delete"
      confirm-color="error"
      @confirm="confirmDelete"
    />
    <WarningDialog
      v-model="repairDialog"
      :message="repairMessage"
      confirm-label="Repair"
      @confirm="confirmRepair"
    />
    <WarningDialog
      v-model="leaveDialog"
      :message="leaveMessage"
      confirm-label="Leave anyway"
      confirm-color="error"
      cancel-label="Stay on this page"
      :persistent="true"
      :close-on-outside="false"
      :close-on-esc="false"
      @confirm="confirmLeave"
      @input="onLeaveDialogInput"
    />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'
import { NavigationGuardNext, Route } from 'vue-router'

import WarningDialog from '@/components/common/WarningDialog.vue'
import McapVideoPlayer from '@/components/records/McapVideoPlayer.vue'
import { McapVideoSummary, readMcapVideoSummary } from '@/libs/mcap/player'
import { extractMcapThumbnail } from '@/libs/mcap/thumbnail'
import { deleteCachedThumbnail, getCachedThumbnail, setCachedThumbnail } from '@/libs/mcap/thumbnail-cache'
import { OneMoreTime } from '@/one-more-time'
import autopilot_data from '@/store/autopilot'
import records_store from '@/store/records'
import { RecordingFile, RecordingState } from '@/types/records'
import { prettifySize } from '@/utils/helper_functions'

const ALL_DATES = ''
/** Rewrite speed seen on a Pi 4 SD card, only used to estimate a repair before one is running. */
const REPAIR_BYTES_PER_SECOND = 25 * 1024 * 1024
const LAYOUT_STORAGE_KEY = 'blueos.records.layout'

function storedLayout(): 'cards' | 'table' {
  try {
    return window.localStorage.getItem(LAYOUT_STORAGE_KEY) === 'table' ? 'table' : 'cards'
  } catch {
    return 'cards'
  }
}

interface RecordingTableItem {
  path: string
  file: RecordingFile
  name: string
  state: RecordingState
  size_bytes: number
  created: number
  duration: number
}

function utcCalendarDay(timestamp: number): string {
  const date = new Date(timestamp * 1000)
  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatUtcDayLabel(day: string): string {
  const [year, month, date] = day.split('-')
  return `${year}-${month}-${date} UTC`
}

export default Vue.extend({
  name: 'RecordsView',
  components: {
    McapVideoPlayer,
    WarningDialog,
  },
  beforeRouteLeave(_to: Route, _from: Route, next: NavigationGuardNext): void {
    if (!this.pageBusy) {
      next()
      return
    }
    this.pendingLeave = next
    this.leaveDialog = true
  },
  data() {
    return {
      playerOpen: false,
      playerBusy: false,
      activeRecord: null as RecordingFile | null,
      selectedDate: ALL_DATES,
      layout: storedLayout() as 'cards' | 'table',
      tableSortBy: 'created',
      tableSortDesc: true,
      summaries: {} as Record<string, McapVideoSummary>,
      thumbnails: {} as Record<string, string>,
      thumbnailFailed: {} as Record<string, boolean>,
      thumbnailController: null as AbortController | null,
      summaryController: null as AbortController | null,
      statusPoller: null as OneMoreTime | null,
      selectedPaths: [] as string[],
      deleteDialog: false,
      deleteTargets: [] as RecordingFile[],
      repairDialog: false,
      repairTargets: [] as RecordingFile[],
      leaveDialog: false,
      pendingLeave: null as NavigationGuardNext | null,
      bulkDownloading: false,
      bulkRepairing: false,
      leaveMessage: 'Keep this page open. Downloads and exports run in this browser and will stop if you leave.'
        + ' Repair on the vehicle continues, but you would lose progress shown here.',
    }
  },
  computed: {
    isSafe(): boolean {
      return autopilot_data.is_safe
    },
    recordings(): RecordingFile[] {
      return records_store.recordings
    },
    failedRepairs() {
      return records_store.failed_repairs
    },
    /** Percentage, read/total bytes and time left of every repair the vehicle is running, by path. */
    repairProgress(): Record<string, { percent: number, label: string }> {
      const progress: Record<string, { percent: number, label: string }> = {}
      for (const file of records_store.processing_files) {
        if (!file.total_bytes) {
          continue
        }
        const read = file.bytes_processed ?? 0
        const speed = file.bytes_per_second ?? 0
        const read_label = `${this.formatSize(read)} of ${this.formatSize(file.total_bytes)}`
        const left = speed > 0 ? this.formatDuration((file.total_bytes - read) / speed) : null
        progress[file.path] = {
          percent: Math.min(100, read / file.total_bytes * 100),
          label: left === null ? read_label : `${read_label} · ${left} left`,
        }
      }
      return progress
    },
    loading(): boolean {
      return records_store.loading
    },
    error(): string | null {
      return records_store.error
    },
    dateFilterOptions(): { text: string, value: string }[] {
      const days = new Set(this.recordings.map((file) => utcCalendarDay(file.created)))
      const sorted = Array.from(days).sort((left, right) => right.localeCompare(left))
      return [
        { text: 'All dates', value: ALL_DATES },
        ...sorted.map((day) => ({ text: formatUtcDayLabel(day), value: day })),
      ]
    },
    tableHeaders(): { text: string, value: string, sortable?: boolean, align?: string, width?: string }[] {
      return [
        {
          text: '', value: 'preview', sortable: false, width: '88px',
        },
        { text: 'Name', value: 'name' },
        { text: 'State', value: 'state' },
        { text: 'Size', value: 'size_bytes' },
        { text: 'Created', value: 'created' },
        { text: 'Duration', value: 'duration' },
        { text: 'Tracks', value: 'tracks', sortable: false },
        {
          text: '', value: 'actions', sortable: false, align: 'end',
        },
      ]
    },
    filteredRecordings(): RecordingFile[] {
      if (!this.selectedDate) {
        return this.recordings
      }
      return this.recordings.filter((file) => utcCalendarDay(file.created) === this.selectedDate)
    },
    tableItems(): RecordingTableItem[] {
      return this.filteredRecordings.map((file) => this.tableRow(file))
    },
    selectedTableItems: {
      get(): RecordingTableItem[] {
        const selected = new Set(this.selectedPaths)
        return this.tableItems.filter((item) => selected.has(item.path))
      },
      set(items: RecordingTableItem[]) {
        this.onTableSelect(items)
      },
    },
    selectedFiles(): RecordingFile[] {
      const selected = new Set(this.selectedPaths)
      return this.filteredRecordings.filter((file) => selected.has(file.path))
    },
    allFilteredSelected(): boolean {
      return this.filteredRecordings.length > 0
        && this.filteredRecordings.every((file) => this.selectedPaths.includes(file.path))
    },
    someFilteredSelected(): boolean {
      return this.filteredRecordings.some((file) => this.selectedPaths.includes(file.path))
    },
    selectionStats(): string {
      const files = this.selectedFiles
      const size = files.reduce((total, file) => total + file.size_bytes, 0)
      const duration = files.reduce((total, file) => total + (this.durationSeconds(file) ?? 0), 0)
      return `${this.formatDuration(duration)} · ${this.formatSize(size)}`
    },
    canDownloadSelected(): boolean {
      return this.selectedFiles.some((file) => this.canDownload(file))
    },
    canRepairSelected(): boolean {
      return this.selectedFiles.some((file) => this.canRepair(file))
    },
    canDeleteSelected(): boolean {
      return this.selectedFiles.some((file) => this.canDelete(file))
    },
    pageBusy(): boolean {
      return this.playerBusy || this.bulkDownloading || this.bulkRepairing
    },
    deleteMessage(): string {
      if (this.deleteTargets.length === 1) {
        return `Delete ${this.deleteTargets[0].name}? This cannot be undone.`
      }
      return `Delete ${this.deleteTargets.length} recordings? This cannot be undone.`
    },
    repairMessage(): string {
      const bytes = this.repairTargets.reduce((total, file) => total + file.size_bytes, 0)
      const seconds = bytes / REPAIR_BYTES_PER_SECOND
      const estimate = seconds < 60 ? 'less than a minute' : `around ${this.formatDuration(seconds)}`
      const what = this.repairTargets.length === 1
        ? this.repairTargets[0].name
        : `${this.repairTargets.length} recordings`
      return `Repairing ${what} rewrites ${this.formatSize(bytes)} on the vehicle and should take ${estimate},`
        + ' keeping its disk and processor busy the whole time. Recording and streaming will be slower while it'
        + ' runs. You can already play this recording without repairing it, and you can stop the repair at any'
        + ' time.'
    },
    activeRecordMeta(): string | null {
      const file = this.activeRecord
      if (!file) {
        return null
      }
      const parts: string[] = []
      const duration = this.durationSeconds(file)
      if (duration !== null) {
        parts.push(this.formatDuration(duration))
      }
      const summary = this.summaries[file.path]
      if (summary && summary.tracks.length > 0) {
        parts.push(`${summary.tracks.length} stream${summary.tracks.length === 1 ? '' : 's'}`)
      }
      parts.push(this.formatSize(file.size_bytes))
      return parts.join(' · ')
    },
    needsPolling(): boolean {
      return this.recordings.some(
        (file) => file.state === 'recording' || file.state === 'repairing',
      )
    },
  },
  watch: {
    isSafe(safe: boolean) {
      if (safe) {
        this.refresh()
        this.syncStatusPoller(this.needsPolling)
        return
      }
      this.pauseNetworkActivity()
      this.syncStatusPoller(false)
    },
    needsPolling(active: boolean) {
      this.syncStatusPoller(active)
    },
    recordings() {
      const known = new Set(this.recordings.map((file) => file.path))
      this.selectedPaths = this.selectedPaths.filter((path) => known.has(path))
    },
    pageBusy(busy: boolean) {
      this.syncLeaveGuard(busy)
    },
    layout(value: 'cards' | 'table') {
      try {
        window.localStorage.setItem(LAYOUT_STORAGE_KEY, value)
      } catch {
        // Private mode or quota: the current session still keeps the choice.
      }
    },
  },
  mounted() {
    if (this.isSafe) {
      this.refresh()
    }
    this.statusPoller = new OneMoreTime(
      { delay: 5000, disposeWith: this, autostart: false },
      async () => {
        if (!this.isSafe || !this.needsPolling) {
          return
        }
        await records_store.fetchRecordings()
        if (!this.isSafe) {
          return
        }
        await records_store.fetchProcessingStatus()
        await this.loadSummaries()
      },
    )
    this.syncStatusPoller(this.needsPolling)
    this.syncLeaveGuard(this.pageBusy)
  },
  beforeDestroy() {
    this.syncLeaveGuard(false)
    this.pauseNetworkActivity()
    Object.values(this.thumbnails).forEach((url) => URL.revokeObjectURL(url))
  },
  methods: {
    syncLeaveGuard(busy: boolean): void {
      if (busy) {
        window.addEventListener('beforeunload', this.onBeforeUnload)
        return
      }
      window.removeEventListener('beforeunload', this.onBeforeUnload)
    },
    onBeforeUnload(event: BeforeUnloadEvent): void {
      if (!this.pageBusy) {
        return
      }
      event.preventDefault()
      event.returnValue = this.leaveMessage
    },
    onLeaveDialogInput(open: boolean): void {
      if (open || !this.pendingLeave) {
        return
      }
      this.pendingLeave(false)
      this.pendingLeave = null
    },
    confirmLeave(): void {
      const next = this.pendingLeave
      this.pendingLeave = null
      this.leaveDialog = false
      this.syncLeaveGuard(false)
      next?.()
    },
    isSelected(file: RecordingFile): boolean {
      return this.selectedPaths.includes(file.path)
    },
    toggleSelected(file: RecordingFile): void {
      if (this.isSelected(file)) {
        this.selectedPaths = this.selectedPaths.filter((path) => path !== file.path)
        return
      }
      this.selectedPaths = [...this.selectedPaths, file.path]
    },
    toggleSelectAllFiltered(selected: boolean): void {
      if (selected) {
        this.selectedPaths = this.filteredRecordings.map((file) => file.path)
        return
      }
      this.selectedPaths = []
    },
    clearSelection(): void {
      this.selectedPaths = []
    },
    onTableSelect(items: RecordingTableItem[]): void {
      const visible = new Set(this.tableItems.map((item) => item.path))
      const hiddenSelected = this.selectedPaths.filter((path) => !visible.has(path))
      this.selectedPaths = [...hiddenSelected, ...items.map((item) => item.path)]
    },
    tableRow(file: RecordingFile): RecordingTableItem {
      return {
        path: file.path,
        file,
        name: this.recordingTitle(file),
        state: file.state,
        size_bytes: file.size_bytes,
        created: file.created,
        duration: this.durationSeconds(file) ?? -1,
      }
    },
    onPlayerBusy(busy: boolean): void {
      this.playerBusy = busy
    },
    onPlayerSummary(summary: McapVideoSummary): void {
      const path = this.activeRecord?.path
      if (!path) {
        return
      }
      this.$set(this.summaries, path, summary)
    },
    syncStatusPoller(active: boolean): void {
      this.statusPoller?.setActive(active && this.isSafe)
    },
    pauseNetworkActivity(): void {
      this.thumbnailController?.abort()
      this.thumbnailController = null
      this.summaryController?.abort()
      this.summaryController = null
      if (this.playerOpen) {
        this.playerOpen = false
        this.activeRecord = null
        this.playerBusy = false
      }
    },
    async refresh(): Promise<void> {
      if (!this.isSafe) {
        return
      }
      await Promise.all([
        records_store.fetchRecordings(),
        records_store.fetchProcessingStatus(),
      ])
      if (!this.isSafe) {
        return
      }
      await this.loadSummaries()
    },
    readyFiles(): RecordingFile[] {
      return this.recordings.filter((file) => file.state === 'ready')
    },
    async loadSummaries(): Promise<void> {
      if (!this.isSafe) {
        return
      }
      this.summaryController?.abort()
      const controller = new AbortController()
      this.summaryController = controller
      const pending = this.readyFiles().filter(
        (file) => !this.summaries[file.path],
      )
      try {
        for (const file of pending) {
          if (!this.isSafe || controller.signal.aborted) {
            return
          }
          try {
            // eslint-disable-next-line no-await-in-loop
            this.$set(
              this.summaries,
              file.path,
              await readMcapVideoSummary(file.stream_url, controller.signal),
            )
          } catch (error) {
            if (controller.signal.aborted || !this.isSafe) {
              return
            }
            console.warn(`Failed to read video summary for ${file.name}:`, error)
          }
        }
      } finally {
        if (this.summaryController === controller) {
          this.summaryController = null
        }
      }
      await this.loadThumbnails()
    },
    async loadThumbnails(): Promise<void> {
      if (!this.isSafe) {
        return
      }
      const pending = this.readyFiles().filter((file) => {
        if (this.thumbnails[file.path] || this.thumbnailFailed[file.path]) {
          return false
        }
        const summary = this.summaries[file.path]
        return Boolean(summary?.tracks.some((track) => track.frameCount > 0))
      })
      for (const file of pending) {
        if (!this.isSafe || this.playerOpen) {
          return
        }
        // eslint-disable-next-line no-await-in-loop
        await this.loadThumbnail(file)
      }
    },
    async loadThumbnail(file: RecordingFile): Promise<void> {
      const cacheKey = {
        path: file.path,
        sizeBytes: file.size_bytes,
        modified: file.created,
      }
      const cached = await getCachedThumbnail(cacheKey)
      if (cached) {
        this.rememberThumbnail(file.path, cached)
        return
      }
      if (!this.isSafe) {
        return
      }

      this.thumbnailController?.abort()
      const controller = new AbortController()
      this.thumbnailController = controller
      try {
        const blob = await extractMcapThumbnail(file.stream_url, { signal: controller.signal })
        if (!blob || controller.signal.aborted || !this.isSafe) {
          if (!blob && this.isSafe) {
            this.$set(this.thumbnailFailed, file.path, true)
          }
          return
        }
        await setCachedThumbnail(cacheKey, blob)
        this.rememberThumbnail(file.path, blob)
      } catch (error) {
        if (controller.signal.aborted || !this.isSafe) {
          return
        }
        this.$set(this.thumbnailFailed, file.path, true)
        console.warn(`Failed to build a preview for ${file.name}:`, error)
      } finally {
        if (this.thumbnailController === controller) {
          this.thumbnailController = null
        }
      }
    },
    rememberThumbnail(path: string, blob: Blob): void {
      const previous = this.thumbnails[path]
      if (previous) {
        URL.revokeObjectURL(previous)
      }
      this.$set(this.thumbnails, path, URL.createObjectURL(blob))
    },
    forgetThumbnail(path: string): void {
      const url = this.thumbnails[path]
      if (url) {
        URL.revokeObjectURL(url)
      }
      this.$delete(this.thumbnails, path)
      this.$delete(this.thumbnailFailed, path)
    },
    forgetSummary(path: string): void {
      const file = this.recordings.find((recording) => recording.path === path)
      if (file) {
        deleteCachedThumbnail({
          path: file.path,
          sizeBytes: file.size_bytes,
          modified: file.created,
        }).catch(() => undefined)
      }
      this.forgetThumbnail(path)
      this.$delete(this.summaries, path)
    },
    thumbnailUrl(file: RecordingFile): string | null {
      return this.thumbnails[file.path] ?? null
    },
    recordingTitle(file: RecordingFile): string {
      return file.name.replace(/\.mcap$/i, '')
    },
    repairFailure(file: RecordingFile): string | null {
      return this.failedRepairs.find((failure) => failure.path === file.path)?.error ?? null
    },
    /** A missing index is not a missing recording: the vehicle indexes what was written on demand. */
    canPlay(file: RecordingFile): boolean {
      return file.state === 'ready' || file.state === 'recording' || file.state === 'needs_repair'
    },
    openPlayerFromRow(item: RecordingTableItem): void {
      if (this.canPlay(item.file)) {
        this.openPlayer(item.file)
      }
    },
    canDelete(file: RecordingFile): boolean {
      return this.isSafe && file.state !== 'recording' && file.state !== 'repairing'
    },
    canRepair(file: RecordingFile): boolean {
      return this.isSafe && file.state === 'needs_repair'
    },
    canDownload(file: RecordingFile): boolean {
      if (!this.isSafe) {
        return false
      }
      return file.state === 'ready' || file.state === 'recording'
    },
    deleteTooltip(file: RecordingFile): string {
      if (file.state === 'recording') {
        return 'Cannot delete while the vehicle is still recording'
      }
      if (file.state === 'repairing') {
        return 'Cannot delete while the recording is being repaired'
      }
      return `Delete ${file.name}`
    },
    downloadTooltip(file: RecordingFile): string {
      if (file.state === 'needs_repair') {
        return 'Repair the recording before downloading'
      }
      if (file.state === 'repairing') {
        return 'Wait until repair finishes before downloading'
      }
      if (file.state === 'recording') {
        return 'Download what has been written so far'
      }
      return `Download ${file.name}`
    },
    stateChipColor(state: RecordingState): string {
      const colors: Record<RecordingState, string> = {
        recording: 'warning',
        needs_repair: 'error',
        repairing: 'primary',
        ready: 'success',
      }
      return colors[state]
    },
    stateChipLabel(file: RecordingFile): string {
      const labels: Record<RecordingState, string> = {
        recording: 'Recording',
        needs_repair: 'Needs repair',
        repairing: 'Repairing',
        ready: 'Ready',
      }
      const label = labels[file.state]
      const progress = this.repairProgress[file.path]
      return file.state === 'repairing' && progress ? `${label} ${Math.round(progress.percent)}%` : label
    },
    durationSeconds(file: RecordingFile): number | null {
      if (file.state === 'recording') {
        return Math.max(0, Date.now() / 1000 - file.created)
      }
      const summary = this.summaries[file.path]
      if (!summary) {
        return null
      }
      return summary.durationSeconds
    },
    durationLabel(file: RecordingFile): string | null {
      const duration = this.durationSeconds(file)
      if (duration === null) {
        return null
      }
      return this.formatDuration(duration)
    },
    endedLabel(file: RecordingFile): string | null {
      const summary = this.summaries[file.path]
      if (!summary) {
        return null
      }
      return this.formatDate(summary.ended)
    },
    tracksLabel(file: RecordingFile): string | null {
      const summary = this.summaries[file.path]
      if (!summary) {
        return null
      }
      const videoNames = summary.tracks.map((track) => track.name)
      const otherCount = summary.channels.length - summary.tracks.length
      if (videoNames.length === 0 && otherCount === 0) {
        return 'no topics'
      }
      const parts: string[] = []
      if (videoNames.length > 0) {
        parts.push(videoNames.join(', '))
      }
      if (otherCount > 0) {
        parts.push(`${otherCount} other topic${otherCount === 1 ? '' : 's'}`)
      }
      return parts.join(' · ')
    },
    async repair(file: RecordingFile): Promise<void> {
      if (!this.canRepair(file)) {
        return
      }
      await records_store.repairRecording(file)
      await records_store.fetchRecordings()
      this.syncStatusPoller(this.needsPolling)
    },
    async downloadRecording(file: RecordingFile): Promise<void> {
      if (!this.canDownload(file)) {
        return
      }
      this.triggerDownload(file.download_url, file.name)
    },
    async downloadSelected(): Promise<void> {
      const files = this.selectedFiles.filter((file) => this.canDownload(file))
      if (files.length === 0) {
        return
      }
      this.bulkDownloading = true
      try {
        for (const file of files) {
          // eslint-disable-next-line no-await-in-loop
          await this.downloadRecording(file)
        }
      } finally {
        this.bulkDownloading = false
      }
    },
    askRepair(files: RecordingFile[]): void {
      const targets = files.filter((file) => this.canRepair(file))
      if (targets.length === 0) {
        return
      }
      this.repairTargets = targets
      this.repairDialog = true
    },
    async confirmRepair(): Promise<void> {
      const targets = this.repairTargets
      this.repairTargets = []
      this.bulkRepairing = true
      try {
        for (const file of targets) {
          // eslint-disable-next-line no-await-in-loop
          await this.repair(file)
        }
      } finally {
        this.bulkRepairing = false
      }
    },
    async cancelRepair(file: RecordingFile): Promise<void> {
      await records_store.cancelRepair(file)
      await records_store.fetchRecordings()
    },
    triggerDownload(url: string, filename: string): void {
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      link.click()
    },
    formatDuration(seconds: number): string {
      const total = Math.max(0, Math.round(seconds))
      const days = Math.floor(total / 86400)
      const hours = Math.floor(total % 86400 / 3600)
      const minutes = Math.floor(total % 3600 / 60)
      const rest = total % 60
      const padded_minutes = String(minutes).padStart(2, '0')
      const padded_seconds = String(rest).padStart(2, '0')
      if (days > 0) {
        return `${days}d ${hours}h ${padded_minutes}m`
      }
      if (hours > 0) {
        return `${hours}h ${padded_minutes}m ${padded_seconds}s`
      }
      return `${minutes}m ${padded_seconds}s`
    },
    askDelete(files: RecordingFile[]): void {
      const targets = files.filter((file) => this.canDelete(file))
      if (targets.length === 0) {
        return
      }
      this.deleteTargets = targets
      this.deleteDialog = true
    },
    async confirmDelete(): Promise<void> {
      const targets = this.deleteTargets
      this.deleteTargets = []
      for (const file of targets) {
        // eslint-disable-next-line no-await-in-loop
        await this.deleteRecording(file)
      }
    },
    async deleteRecording(file: RecordingFile): Promise<void> {
      if (!this.canDelete(file)) {
        return
      }
      await deleteCachedThumbnail({
        path: file.path,
        sizeBytes: file.size_bytes,
        modified: file.created,
      })
      this.forgetThumbnail(file.path)
      this.forgetSummary(file.path)
      if (this.activeRecord?.path === file.path) {
        this.playerOpen = false
        this.activeRecord = null
        this.playerBusy = false
      }
      await records_store.deleteRecording(file)
    },
    openPlayer(file: RecordingFile): void {
      if (!this.canPlay(file) || !this.isSafe) {
        return
      }
      this.thumbnailController?.abort()
      this.activeRecord = file
      this.playerOpen = true
    },
    closePlayer(): void {
      if (this.playerBusy) {
        return
      }
      this.playerOpen = false
      this.activeRecord = null
      this.loadThumbnails()
    },
    formatSize(bytes: number): string {
      return prettifySize(bytes / 1024)
    },
    formatDate(timestamp: number): string {
      const date = new Date(timestamp * 1000)
      return date.toLocaleString()
    },
  },
})
</script>

<style scoped>
.records-view {
  position: relative;
  min-height: 100%;
}

.record-card {
  height: 100%;
  overflow: hidden;
}

.record-card-wrap {
  position: relative;
  height: 100%;
}

.card-select {
  position: absolute;
  top: 4px;
  left: 8px;
  z-index: 2;
}

.preview-wrapper {
  position: relative;
}

.record-preview {
  position: relative;
  overflow: hidden;
  height: 180px;
}

.preview-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.preview-overlay {
  position: relative;
  z-index: 1;
  width: 100%;
  height: 100%;
  padding: 8px;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0.15));
}

.preview-caption {
  color: rgba(255, 255, 255, 0.9);
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
}

.play-btn {
  background-color: rgba(255, 255, 255, 0.85) !important;
  pointer-events: all;
}

.preview-clickable {
  cursor: pointer;
}

.player-card {
  position: relative;
  max-height: 100%;
}

.date-filter {
  max-width: 280px;
  min-width: 200px;
}

.records-table ::v-deep tbody tr {
  cursor: pointer;
}

.table-preview {
  position: relative;
  width: 72px;
  height: 40px;
  overflow: hidden;
  border-radius: 4px;
}

.table-preview-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.toolbar {
  gap: 4px;
}

.min-width-0 {
  min-width: 0;
}

.mr-2 {
  margin-right: 8px;
}
</style>
