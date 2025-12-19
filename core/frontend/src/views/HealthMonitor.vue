<template>
  <v-card height="100%">
    <v-tabs
      v-model="activeTab"
      centered
      icons-and-text
      show-arrows
    >
      <v-tabs-slider />
      <v-tab>
        Active Issues
        <v-icon>mdi-alert-circle</v-icon>
      </v-tab>
      <v-tab>
        History
        <v-icon>mdi-history</v-icon>
      </v-tab>
    </v-tabs>

    <v-tabs-items v-model="activeTab">
      <v-tab-item>
        <v-container fluid>
          <v-row v-if="error">
            <v-col cols="12">
              <v-alert type="error" dense outlined>
                {{ error }}
              </v-alert>
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12" md="4">
              <v-select
                v-model="selectedSeverity"
                :items="severityOptions"
                label="Severity"
                clearable
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-select
                v-model="selectedSource"
                :items="sourceOptions"
                label="Source"
                clearable
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="search"
                label="Search"
                clearable
              />
            </v-col>
          </v-row>

          <v-row v-if="loading">
            <v-col cols="12">
              <v-progress-linear
                color="primary"
                indeterminate
                height="6"
                rounded
              />
            </v-col>
          </v-row>

          <v-row v-else>
            <v-col cols="12">
              <v-alert
                v-if="filteredActive.length === 0"
                type="success"
                outlined
                dense
              >
                No active issues detected.
              </v-alert>
              <v-data-table
                v-else
                :headers="activeHeaders"
                :items="filteredActive"
                item-key="id"
                dense
                class="elevation-1"
              >
                <template #item.severity="{ item }">
                  <v-chip
                    small
                    :color="severityColor(item.severity)"
                    dark
                  >
                    {{ item.severity }}
                  </v-chip>
                </template>
                <template #item.timestamp="{ item }">
                  {{ formatTimestamp(item.timestamp) }}
                </template>
                <template #item.details="{ item }">
                  <div class="details-cell">
                    {{ item.details }}
                  </div>
                </template>
              </v-data-table>
            </v-col>
          </v-row>
        </v-container>
      </v-tab-item>

      <v-tab-item>
        <v-container fluid>
          <v-row>
            <v-col cols="12" md="4">
              <v-select
                v-model="historySeverity"
                :items="severityOptions"
                label="Severity"
                clearable
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-select
                v-model="historySource"
                :items="sourceOptions"
                label="Source"
                clearable
              />
            </v-col>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="historySearch"
                label="Search"
                clearable
              />
            </v-col>
          </v-row>

          <v-row>
            <v-col cols="12">
              <v-data-table
                :headers="historyHeaders"
                :items="filteredHistory"
                item-key="timestamp"
                dense
                class="elevation-1"
              >
                <template #item.type="{ item }">
                  <v-chip
                    small
                    :color="eventColor(item.type)"
                    dark
                  >
                    {{ item.type }}
                  </v-chip>
                </template>
                <template #item.severity="{ item }">
                  <v-chip
                    small
                    :color="severityColor(item.severity)"
                    dark
                  >
                    {{ item.severity }}
                  </v-chip>
                </template>
                <template #item.timestamp="{ item }">
                  {{ formatTimestamp(item.timestamp) }}
                </template>
                <template #item.details="{ item }">
                  <div class="details-cell">
                    {{ item.details }}
                  </div>
                </template>
              </v-data-table>
            </v-col>
          </v-row>
        </v-container>
      </v-tab-item>
    </v-tabs-items>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import health_monitor from '@/store/health_monitor'
import { HealthEvent, HealthProblem } from '@/types/health-monitor'

export default Vue.extend({
  name: 'HealthMonitor',
  data() {
    return {
      activeTab: 0,
      selectedSeverity: null as string | null,
      selectedSource: null as string | null,
      search: '',
      historySeverity: null as string | null,
      historySource: null as string | null,
      historySearch: '',
      refreshTimer: null as number | null,
      activeHeaders: [
        { text: 'Severity', value: 'severity' },
        { text: 'Title', value: 'title' },
        { text: 'Source', value: 'source' },
        { text: 'Last Update', value: 'timestamp' },
        { text: 'Details', value: 'details' },
      ],
      historyHeaders: [
        { text: 'Type', value: 'type' },
        { text: 'Severity', value: 'severity' },
        { text: 'Title', value: 'title' },
        { text: 'Source', value: 'source' },
        { text: 'Timestamp', value: 'timestamp' },
        { text: 'Details', value: 'details' },
      ],
    }
  },
  computed: {
    summary() {
      return health_monitor.summary
    },
    history() {
      return health_monitor.history
    },
    loading() {
      return health_monitor.loading
    },
    error() {
      return health_monitor.error
    },
    severityOptions(): string[] {
      return ['info', 'warn', 'error', 'critical']
    },
    sourceOptions(): string[] {
      return ['system', 'vehicle', 'extension', 'network']
    },
    filteredActive(): HealthProblem[] {
      const issues = this.summary?.active ?? []
      return issues.filter((issue) => this.matchesFilters(
        issue,
        this.selectedSeverity,
        this.selectedSource,
        this.search,
      ))
    },
    filteredHistory(): HealthEvent[] {
      const events = this.history?.events ?? []
      return events.filter((event) => this.matchesFilters(
        event,
        this.historySeverity,
        this.historySource,
        this.historySearch,
      ))
    },
  },
  mounted() {
    this.refresh()
    this.refreshTimer = window.setInterval(() => {
      this.refresh()
    }, 10000)
  },
  beforeDestroy() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
      this.refreshTimer = null
    }
  },
  methods: {
    refresh() {
      health_monitor.fetchSummary()
      health_monitor.fetchHistory()
    },
    matchesFilters(
      item: HealthProblem,
      severity: string | null,
      source: string | null,
      text: string,
    ): boolean {
      if (severity && item.severity !== severity) {
        return false
      }
      if (source && item.source !== source) {
        return false
      }
      if (text) {
        const needle = text.toLowerCase()
        return [item.title, item.details, item.id].some(
          (field) => field?.toLowerCase().includes(needle),
        )
      }
      return true
    },
    severityColor(severity: string): string {
      switch (severity) {
        case 'critical':
          return 'red darken-3'
        case 'error':
          return 'red'
        case 'warn':
          return 'orange darken-2'
        default:
          return 'blue'
      }
    },
    eventColor(eventType: string): string {
      switch (eventType) {
        case 'problem_detected':
          return 'red darken-2'
        case 'problem_resolved':
          return 'green'
        case 'problem_updated':
          return 'blue'
        default:
          return 'grey'
      }
    },
    formatTimestamp(timestamp: number): string {
      return new Date(timestamp).toLocaleString()
    },
  },
})
</script>

<style scoped>
.details-cell {
  max-width: 480px;
  white-space: normal;
}
</style>
