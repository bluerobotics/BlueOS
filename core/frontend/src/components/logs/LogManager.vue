<template>
  <v-container>
    <v-card
      v-if="logs_fetched"
      elevation="1"
    >
      <v-card-title class="ma-4">
        Autopilot logs
        <v-spacer />
        <v-btn
          v-tooltip="'Fetch available logs'"
          icon
          @click="fetchAvailableLogs"
        >
          <v-icon>mdi-update</v-icon>
        </v-btn>
        <v-btn
          v-tooltip="'Download selected logs'"
          icon
          color="success"
          :disabled="disable_batch_operations || deleting"
          @click="downloadSelectedLogs"
        >
          <v-icon>mdi-download-multiple</v-icon>
        </v-btn>
        <v-btn
          v-tooltip="'Delete selected logs'"
          icon
          color="error"
          :disabled="disable_batch_operations || downloading"
          @click="removeLogs"
        >
          <v-icon>mdi-trash-can</v-icon>
        </v-btn>
      </v-card-title>
      <v-card-text>
        <v-data-table
          v-model="selected_logs"
          :headers="headers"
          :items="parsed_logs"
          item-key="name"
          show-select
          :sort-by.sync="sortBy"
          :sort-desc.sync="sortDesc"
        >
          <template #item.size="{ item }">
            {{ printSize(item.size) }}
          </template>
          <template #item.actions="{ item }">
            <v-btn
              v-tooltip="'Open log in UAV Log Viewer'"
              icon
              color="green"
              @click="replay_log(item)"
            >
              <v-icon>mdi-play</v-icon>
            </v-btn>
            <v-btn
              v-tooltip="'Download log'"
              icon
              :disabled="deleting"
              @click="downloadLogs([item])"
            >
              <v-icon>mdi-download</v-icon>
            </v-btn>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
    <v-container v-else>
      <spinning-logo
        size="30%"
        subtitle="Fetching available logs..."
      />
    </v-container>
  </v-container>
</template>

<script lang="ts">
import { format } from 'date-fns'
import Vue from 'vue'

import filebrowser from '@/libs/filebrowser'
import { FilebrowserFile } from '@/types/filebrowser'
import { prettifySize } from '@/utils/helper_functions'

import SpinningLogo from '../common/SpinningLogo.vue'

export default Vue.extend({
  name: 'LogManager',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      sortBy: 'modified',
      sortDesc: true,
      available_logs: [] as FilebrowserFile[],
      logs_fetched: false,
      selected_logs: [] as FilebrowserFile[],
      deleting: false,
      downloading: false,
      headers: [
        {
          text: 'Name',
          align: 'start',
          sortable: false,
          value: 'name',
        },
        { text: 'Size', value: 'size' },
        { text: 'Type', value: 'extension' },
        { text: 'Modified', value: 'modified' },
        {
          text: 'Actions',
          align: 'end',
          sortable: false,
          value: 'actions',
        },
      ],
    }
  },
  computed: {
    disable_batch_operations(): boolean {
      return this.selected_logs.isEmpty()
    },
    parsed_logs(): FilebrowserFile[] {
      return this.available_logs.map((log) => ({
        ...log,
        modified: format(new Date(log.modified), 'yyyy-MM-dd HH:mm:ss'),
      }))
    },
  },
  async mounted() {
    await this.fetchAvailableLogs()
  },
  methods: {
    async fetchAvailableLogs(): Promise<void> {
      const new_logs: FilebrowserFile[] = []

      const log_folders = ['/ardupilot_logs/firmware/logs/', '/ardupilot_logs/logs/']

      // We fetch all paths in parallel and wait for everything to finish
      // If it fails the folder does not exist, we display a 'No data available' message
      // If it succeeds, it'll populate the array and show the logs to the user
      try {
        // Use allSettled to allow promises to fail in parallel
        await Promise.allSettled(log_folders.map(async (folder_path) => {
          const folder = await filebrowser.fetchFolder(folder_path)
          Array.prototype.push.apply(new_logs, folder.items)
        }))
      } catch (_) {
        // We are going to ignore the error as described on the first comment and
        // continue with the following lines
      }

      this.logs_fetched = true
      // We can have empty log files or really small, we should remove them
      this.available_logs = new_logs.filter(
        (log) => ['.bin', '.tlog'].includes(log.extension.toLowerCase()) && log.size > 100,
      )
    },
    async downloadSelectedLogs(): Promise<void> {
      await this.downloadLogs(this.selected_logs)
      this.selected_logs = []
    },
    async downloadLogs(logs: FilebrowserFile[]): Promise<void> {
      if (this.downloading) return
      this.downloading = true
      try {
        await filebrowser.downloadFiles(logs)
      } finally {
        this.downloading = false
      }
    },
    printSize(size_bytes: number): string {
      return prettifySize(size_bytes / 1024)
    },
    async removeLogs(): Promise<void> {
      if (this.selected_logs.isEmpty()) return

      this.deleting = true
      try {
        await filebrowser.deleteFiles(this.selected_logs)
        await this.fetchAvailableLogs()
        this.selected_logs = []
      } finally {
        this.deleting = false
      }
    },
    async replay_log(log: FilebrowserFile): Promise<void> {
      const log_url = encodeURIComponent(await filebrowser.singleFileRelativeURL(log))
      window.open(`/logviewer/#/?file=${log_url}`)
    },
  },
})
</script>
