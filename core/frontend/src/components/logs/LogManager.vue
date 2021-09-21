<template>
  <v-container>
    <v-card
      v-if="!fetching_logs"
      flat
    >
      <v-card-title>
        Autopilot logs
        <v-spacer />
        <v-btn
          icon
          @click="fetchAvailableLogs"
        >
          <v-icon>mdi-update</v-icon>
        </v-btn>
        <v-btn
          icon
          color="green darken-1"
          :disabled="disable_batch_operations"
          @click="downloadSelectedLogs"
        >
          <v-icon>mdi-download-multiple</v-icon>
        </v-btn>
        <v-btn
          icon
          color="red darken-1"
          :disabled="disable_batch_operations"
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
          <template #item.actions="{ item }">
            <v-icon @click="replay_log(item)">
              mdi-play
            </v-icon>
            <v-icon @click="downloadLogs([item])">
              mdi-download
            </v-icon>
          </template>
        </v-data-table>
      </v-card-text>
    </v-card>
    <v-container v-else>
      <spinning-logo size="30%" />
    </v-container>
  </v-container>
</template>

<script lang="ts">
import { format } from 'date-fns'
import Vue from 'vue'

import filebrowser from '@/libs/filebrowser'
import { FilebrowserFile } from '@/types/filebrowser'

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
      auth_key: '',
      available_logs: [] as FilebrowserFile[],
      fetching_logs: false,
      selected_logs: [] as FilebrowserFile[],
      headers: [
        {
          text: 'Name',
          align: 'start',
          sortable: false,
          value: 'name',
        },
        { text: 'Size (MB)', value: 'size' },
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
      return this.selected_logs.length === 0
    },
    parsed_logs(): FilebrowserFile[] {
      return this.available_logs.map((log) => ({
        ...log,
        modified: format(new Date(log.modified), 'yyyy-MM-dd HH:mm:ss'),
        size: log.size / 1e6,
      }))
    },
    are_logs_available(): boolean {
      return this.available_logs.length !== 0
    },
  },
  async mounted() {
    await this.fetchAvailableLogs()
  },
  methods: {
    async fetchAvailableLogs(): Promise<void> {
      const new_logs: FilebrowserFile[] = []
      this.fetching_logs = true

      const log_folders = ['/root/.config/ardupilot-manager/firmware/logs/', '/root/.config/ardupilot-manager/logs/']

      for (const folder_path of log_folders) {
        await filebrowser.fetchFolder(folder_path)
          .then((folder) => {
            Array.prototype.push.apply(new_logs, folder.items)
          })
      }

      this.available_logs = new_logs.filter((log) => ['.bin', '.tlog'].includes(log.extension.toLowerCase()))
      this.fetching_logs = false
    },
    downloadSelectedLogs(): void {
      this.downloadLogs(this.selected_logs)
      this.selected_logs = []
    },
    downloadLogs(logs: FilebrowserFile[]): void {
      filebrowser.downloadFiles(logs)
    },
    async removeLogs(): Promise<void> {
      if (this.selected_logs.length === 0) return

      await filebrowser.deleteFiles(this.selected_logs)

      await this.fetchAvailableLogs()
      this.selected_logs = []
    },
    async replay_log(log: FilebrowserFile): Promise<void> {
      const log_url = encodeURIComponent(filebrowser.singleFileRelativeURL(log))
      window.open(`/logviewer/#/?file=${log_url}`)
    },
  },
})
</script>
