<template>
  <v-container fluid class="service-manager pa-4">
    <v-row>
      <!-- Service List Panel -->
      <v-col cols="12" md="4" lg="3">
        <v-card class="service-list-card" elevation="2">
          <v-card-title class="d-flex align-center py-2">
            <v-icon left color="primary">
              mdi-cogs
            </v-icon>
            Services
            <v-spacer />
            <v-chip
              small
              :color="running_count === services.length ? 'success' : 'warning'"
            >
              {{ running_count }}/{{ services.length }}
            </v-chip>
            <v-btn
              v-tooltip="'Refresh services'"
              icon
              small
              class="ml-2"
              @click="fetchServices"
            >
              <v-icon small>
                mdi-refresh
              </v-icon>
            </v-btn>
          </v-card-title>
          <v-divider />
          <v-text-field
            v-model="search"
            label="Search services"
            prepend-inner-icon="mdi-magnify"
            clearable
            dense
            outlined
            hide-details
            class="mx-3 mt-3"
          />
          <div
            v-if="!services_loaded"
            class="d-flex flex-column align-center justify-center py-8"
            style="height: calc(100vh - 280px)"
          >
            <v-progress-circular indeterminate color="primary" size="48" />
            <div class="text-body-2 grey--text mt-4">
              Loading services...
            </div>
          </div>
          <v-list v-else dense class="service-list overflow-y-auto" max-height="calc(100vh - 280px)">
            <v-list-item-group v-model="selected_index" color="primary">
              <v-list-item
                v-for="service in filtered_services"
                :key="service.name"
                @click="selectService(service)"
              >
                <v-list-item-icon class="mr-3">
                  <v-icon
                    :color="service.status === 'running' ? 'success' : 'error'"
                    small
                  >
                    {{ service.status === 'running' ? 'mdi-check-circle' : 'mdi-close-circle' }}
                  </v-icon>
                </v-list-item-icon>
                <v-list-item-content>
                  <v-list-item-title class="text-body-2">
                    {{ service.name }}
                  </v-list-item-title>
                  <v-list-item-subtitle v-if="service.pid" class="text-caption">
                    PID: {{ service.pid }}
                  </v-list-item-subtitle>
                </v-list-item-content>
                <v-list-item-action class="my-0">
                  <v-chip
                    v-if="service.restart_count > 0"
                    x-small
                    color="warning"
                    outlined
                  >
                    {{ service.restart_count }}
                  </v-chip>
                </v-list-item-action>
              </v-list-item>
            </v-list-item-group>
          </v-list>
        </v-card>
      </v-col>

      <!-- Service Details Panel -->
      <v-col cols="12" md="8" lg="9">
        <v-card v-if="selected_service" class="service-detail-card" elevation="2">
          <v-card-title class="d-flex align-center py-2">
            <v-icon
              left
              :color="selected_service.status === 'running' ? 'success' : 'error'"
            >
              {{ selected_service.status === 'running' ? 'mdi-play-circle' : 'mdi-stop-circle' }}
            </v-icon>
            {{ selected_service.name }}
            <v-spacer />
            <v-btn-toggle dense class="mr-2">
              <v-btn
                v-tooltip="'Start service'"
                small
                :disabled="selected_service.status === 'running' || action_loading"
                color="success"
                @click="startService"
              >
                <v-icon small>
                  mdi-play
                </v-icon>
              </v-btn>
              <v-btn
                v-tooltip="'Stop service'"
                small
                :disabled="selected_service.status !== 'running' || action_loading"
                color="error"
                @click="stopService"
              >
                <v-icon small>
                  mdi-stop
                </v-icon>
              </v-btn>
              <v-btn
                v-tooltip="'Restart service'"
                small
                :disabled="action_loading"
                color="warning"
                @click="restartService"
              >
                <v-icon small>
                  mdi-restart
                </v-icon>
              </v-btn>
            </v-btn-toggle>
          </v-card-title>
          <v-divider />

          <v-tabs v-model="detail_tab" background-color="transparent">
            <v-tab>
              <v-icon left small>
                mdi-console
              </v-icon>
              Logs
            </v-tab>
            <v-tab>
              <v-icon left small>
                mdi-cog
              </v-icon>
              Configuration
            </v-tab>
            <v-tab>
              <v-icon left small>
                mdi-chart-line
              </v-icon>
              Metrics
            </v-tab>
          </v-tabs>

          <v-tabs-items v-model="detail_tab" class="detail-tabs-content" touchless>
            <!-- Logs Tab -->
            <v-tab-item>
              <v-card flat class="log-container">
                <v-card-actions class="py-1">
                  <v-select
                    v-model="log_lines"
                    :items="log_line_options"
                    label="Lines"
                    dense
                    outlined
                    hide-details
                    style="max-width: 120px"
                  />
                  <v-select
                    v-model="log_stream"
                    :items="stream_options"
                    label="Stream"
                    dense
                    outlined
                    hide-details
                    style="max-width: 120px"
                    class="ml-2"
                  />
                  <v-spacer />
                  <v-btn
                    v-tooltip="'Refresh logs'"
                    icon
                    small
                    :loading="logs_loading"
                    @click="fetchLogs"
                  >
                    <v-icon small>
                      mdi-refresh
                    </v-icon>
                  </v-btn>
                  <v-switch
                    v-model="auto_scroll"
                    v-tooltip="'Auto-scroll'"
                    dense
                    hide-details
                    class="ml-2 mt-0"
                  />
                </v-card-actions>
                <v-divider />
                <div ref="logViewer" class="log-viewer font-mono pa-2">
                  <div
                    v-for="(logLine, idx) in service_logs"
                    :key="idx"
                    class="log-line"
                    :class="{ 'stderr-line': logLine.stream === 'stderr' }"
                  >
                    <span class="log-timestamp">{{ formatTimestamp(logLine.timestamp) }}</span>
                    <span class="log-stream" :class="logLine.stream">{{ logLine.stream }}</span>
                    <!-- eslint-disable-next-line vue/no-v-html -->
                    <span class="log-content" v-html="formatLogContent(logLine.line)" />
                  </div>
                  <div v-if="service_logs.length === 0" class="text-center grey--text pa-8">
                    No logs available
                  </div>
                </div>
              </v-card>
            </v-tab-item>

            <!-- Configuration Tab -->
            <v-tab-item>
              <v-card flat class="pa-4 config-tab-content">
                <h4 class="mb-2">
                  Service Info
                </h4>
                <v-simple-table dense>
                  <tbody>
                    <tr>
                      <td class="font-weight-bold" width="180">
                        Name
                      </td>
                      <td>{{ selected_service.name }}</td>
                    </tr>
                    <tr>
                      <td class="font-weight-bold">
                        Command
                      </td>
                      <td class="font-mono text-body-2">
                        {{ selected_service.command?.join(' ') ?? '' }}
                      </td>
                    </tr>
                    <tr>
                      <td class="font-weight-bold">
                        Custom Command
                      </td>
                      <td>
                        <v-text-field
                          v-model="config_form.command"
                          dense
                          outlined
                          hide-details
                          placeholder="Override command (space-separated)"
                          class="font-mono text-body-2"
                          style="max-width: 500px"
                        />
                      </td>
                    </tr>
                    <tr v-if="selected_service.cwd">
                      <td class="font-weight-bold">
                        Working directory
                      </td>
                      <td class="font-mono text-body-2">
                        {{ selected_service.cwd }}
                      </td>
                    </tr>
                    <tr>
                      <td class="font-weight-bold">
                        Enabled
                      </td>
                      <td>
                        <v-icon :color="selected_service.enabled ? 'success' : 'grey'" small>
                          {{ selected_service.enabled ? 'mdi-check' : 'mdi-close' }}
                        </v-icon>
                      </td>
                    </tr>
                  </tbody>
                </v-simple-table>

                <v-divider class="my-4" />

                <div class="d-flex align-center mb-2">
                  <h4>Behavior Settings</h4>
                  <v-spacer />
                  <v-btn
                    v-tooltip="'Reset to defaults'"
                    small
                    text
                    class="mr-2"
                    @click="resetServiceConfig"
                  >
                    <v-icon left small>
                      mdi-restore
                    </v-icon>
                    Reset
                  </v-btn>
                  <v-btn
                    v-tooltip="'Save configuration changes'"
                    small
                    color="primary"
                    :loading="config_saving"
                    :disabled="!hasConfigChanges"
                    @click="saveConfig"
                  >
                    <v-icon left small>
                      mdi-content-save
                    </v-icon>
                    Save
                  </v-btn>
                </div>
                <v-row dense>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch
                      v-model="config_form.enabled"
                      label="Service enabled"
                      dense
                      hide-details
                      class="mt-0"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-switch
                      v-model="config_form.restart"
                      label="Auto-restart on exit"
                      dense
                      hide-details
                      class="mt-0"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-text-field
                      v-model.number="config_form.restart_delay_sec"
                      label="Restart delay (sec)"
                      type="number"
                      min="0"
                      step="0.5"
                      dense
                      outlined
                      hide-details
                      :disabled="!config_form.restart"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-text-field
                      v-model.number="config_form.stop_timeout_sec"
                      label="Stop timeout (sec)"
                      type="number"
                      min="1"
                      step="1"
                      dense
                      outlined
                      hide-details
                    />
                  </v-col>
                </v-row>

                <v-divider class="my-4" />

                <h4 class="mb-2">
                  Resource Limits (cgroups)
                </h4>
                <p class="text-caption grey--text mb-3">
                  Set resource limits to restrict CPU, memory, and process count.
                  Leave empty or 0 for no limit. Changes apply immediately to running services.
                </p>
                <v-row dense>
                  <v-col cols="12" sm="6" md="4">
                    <v-text-field
                      v-model.number="config_form.limits.cpu_cores"
                      label="CPU cores limit"
                      type="number"
                      min="0"
                      step="0.1"
                      dense
                      outlined
                      hide-details
                      placeholder="e.g., 1.5 = 150% of one core"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-text-field
                      v-model.number="config_form.limits.memory_mb"
                      label="Memory limit (MB)"
                      type="number"
                      min="0"
                      step="64"
                      dense
                      outlined
                      hide-details
                      placeholder="e.g., 512"
                    />
                  </v-col>
                  <v-col cols="12" sm="6" md="4">
                    <v-text-field
                      v-model.number="config_form.limits.max_pids"
                      label="Max processes (PIDs)"
                      type="number"
                      min="0"
                      step="1"
                      dense
                      outlined
                      hide-details
                      placeholder="e.g., 100"
                    />
                  </v-col>
                </v-row>

                <v-divider class="my-4" />

                <h4 class="mb-2">
                  Environment Variables
                </h4>
                <v-simple-table v-if="hasEnvironmentVariables" dense class="env-table">
                  <tbody>
                    <tr v-for="(value, key) in selected_service.env" :key="key">
                      <td class="font-weight-bold font-mono" width="200">
                        {{ key }}
                      </td>
                      <td class="font-mono text-body-2 text-truncate">
                        {{ value }}
                      </td>
                    </tr>
                  </tbody>
                </v-simple-table>
                <div v-else class="grey--text text-body-2">
                  No custom environment variables
                </div>

                <v-divider class="my-4" />

                <h4 class="mb-2">
                  Runtime Status
                </h4>
                <v-simple-table dense>
                  <tbody>
                    <tr>
                      <td class="font-weight-bold" width="180">
                        Status
                      </td>
                      <td>
                        <v-chip
                          small
                          :color="selected_service.status === 'running' ? 'success' : 'error'"
                        >
                          {{ selected_service.status === 'running' ? 'Running' : 'Stopped' }}
                        </v-chip>
                      </td>
                    </tr>
                    <tr v-if="selected_service.pid">
                      <td class="font-weight-bold">
                        PID
                      </td>
                      <td>{{ selected_service.pid }}</td>
                    </tr>
                    <tr v-if="selected_service.started_at">
                      <td class="font-weight-bold">
                        Started at
                      </td>
                      <td>{{ formatDateTime(selected_service.started_at) }}</td>
                    </tr>
                    <tr v-if="selected_service.stopped_at">
                      <td class="font-weight-bold">
                        Stopped at
                      </td>
                      <td>{{ formatDateTime(selected_service.stopped_at) }}</td>
                    </tr>
                    <tr v-if="selected_service.exit_code !== null">
                      <td class="font-weight-bold">
                        Exit code
                      </td>
                      <td>
                        <v-chip
                          small
                          :color="selected_service.exit_code === 0 ? 'success' : 'error'"
                        >
                          {{ selected_service.exit_code }}
                        </v-chip>
                      </td>
                    </tr>
                    <tr>
                      <td class="font-weight-bold">
                        Restart count
                      </td>
                      <td>{{ selected_service.restart_count }}</td>
                    </tr>
                    <tr v-if="selected_service.uptime_seconds">
                      <td class="font-weight-bold">
                        Uptime
                      </td>
                      <td>{{ formatUptime(selected_service.uptime_seconds) }}</td>
                    </tr>
                  </tbody>
                </v-simple-table>
              </v-card>
            </v-tab-item>

            <!-- Metrics Tab -->
            <v-tab-item>
              <v-card flat class="pa-4 metrics-tab-content">
                <template v-if="service_metrics">
                  <!-- Current Values Summary -->
                  <v-row class="mb-4">
                    <v-col cols="6" sm="4">
                      <v-card outlined class="text-center pa-3">
                        <div class="text-h6 primary--text">
                          {{ (service_metrics.cpu_percent ?? 0).toFixed(1) }}%
                        </div>
                        <div class="text-caption grey--text">
                          CPU
                        </div>
                      </v-card>
                    </v-col>
                    <v-col cols="6" sm="4">
                      <v-card outlined class="text-center pa-3">
                        <div class="text-h6 success--text">
                          {{ (service_metrics.memory_mb ?? 0).toFixed(1) }} MB
                        </div>
                        <div class="text-caption grey--text">
                          Memory
                        </div>
                      </v-card>
                    </v-col>
                    <v-col cols="6" sm="4">
                      <v-card outlined class="text-center pa-3">
                        <div class="text-h6 info--text">
                          {{ (service_metrics.swap_mb ?? 0).toFixed(1) }} MB
                        </div>
                        <div class="text-caption grey--text">
                          Swap
                        </div>
                      </v-card>
                    </v-col>
                    <v-col cols="6" sm="6">
                      <v-card outlined class="text-center pa-3">
                        <div class="text-h6 warning--text">
                          {{ formatDiskRate(service_metrics.io_read_rate_mbps, service_metrics.io_write_rate_mbps) }}
                        </div>
                        <div class="text-caption grey--text">
                          Disk I/O
                        </div>
                      </v-card>
                    </v-col>
                    <v-col cols="6" sm="6">
                      <v-card outlined class="text-center pa-3">
                        <div class="text-h6" style="color: #00BCD4">
                          {{ formatNetRate(service_metrics.net_rx_rate_mbps, service_metrics.net_tx_rate_mbps) }}
                        </div>
                        <div class="text-caption grey--text">
                          Network
                        </div>
                      </v-card>
                    </v-col>
                  </v-row>

                  <!-- CPU Chart -->
                  <v-card outlined class="mb-4 pa-3">
                    <div class="d-flex align-center mb-2">
                      <v-icon small color="primary" class="mr-2">
                        mdi-chip
                      </v-icon>
                      <span class="text-subtitle-2">CPU Usage</span>
                    </div>
                    <apexchart
                      v-if="metrics_history.length > 1"
                      type="area"
                      height="150"
                      :options="cpuChartOptions"
                      :series="cpuChartSeries"
                    />
                    <div v-else class="text-center grey--text py-4">
                      Collecting data...
                    </div>
                  </v-card>

                  <!-- Memory & Swap Chart -->
                  <v-card outlined class="mb-4 pa-3">
                    <div class="d-flex align-center mb-2">
                      <v-icon small color="success" class="mr-2">
                        mdi-memory
                      </v-icon>
                      <span class="text-subtitle-2">Memory & Swap</span>
                      <v-spacer />
                      <span class="text-caption">
                        Peak:
                        <span class="success--text">
                          RAM {{ (service_metrics.memory_peak_mb ?? 0).toFixed(1) }} MB
                        </span> /
                        <span class="info--text">
                          Swap {{ (service_metrics.swap_peak_mb ?? 0).toFixed(1) }} MB
                        </span>
                      </span>
                    </div>
                    <apexchart
                      v-if="metrics_history.length > 1"
                      type="area"
                      height="150"
                      :options="memoryChartOptions"
                      :series="memoryChartSeries"
                    />
                    <div v-else class="text-center grey--text py-4">
                      Collecting data...
                    </div>
                  </v-card>

                  <!-- Disk I/O Chart -->
                  <v-card outlined class="mb-4 pa-3">
                    <div class="d-flex align-center mb-2">
                      <v-icon small color="warning" class="mr-2">
                        mdi-harddisk
                      </v-icon>
                      <span class="text-subtitle-2">Disk I/O</span>
                      <v-spacer />
                      <span class="text-caption">
                        Total:
                        <span class="warning--text">R {{ (service_metrics.io_read_mb ?? 0).toFixed(1) }} MB</span> /
                        <span style="color: #9C27B0">W {{ (service_metrics.io_write_mb ?? 0).toFixed(1) }} MB</span>
                      </span>
                    </div>
                    <apexchart
                      v-if="metrics_history.length > 1"
                      type="area"
                      height="150"
                      :options="ioChartOptions"
                      :series="ioChartSeries"
                    />
                    <div v-else class="text-center grey--text py-4">
                      Collecting data...
                    </div>
                  </v-card>

                  <!-- Network I/O Chart -->
                  <v-card outlined class="pa-3">
                    <div class="d-flex align-center mb-2">
                      <v-icon small style="color: #00BCD4" class="mr-2">
                        mdi-network
                      </v-icon>
                      <span class="text-subtitle-2">Network I/O</span>
                      <v-spacer />
                      <span class="text-caption">
                        Total:
                        <span style="color: #00BCD4">RX {{ (service_metrics.net_rx_mb ?? 0).toFixed(1) }} MB</span> /
                        <span style="color: #E91E63">TX {{ (service_metrics.net_tx_mb ?? 0).toFixed(1) }} MB</span>
                      </span>
                    </div>
                    <apexchart
                      v-if="metrics_history.length > 1"
                      type="area"
                      height="150"
                      :options="networkChartOptions"
                      :series="networkChartSeries"
                    />
                    <div v-else class="text-center grey--text py-4">
                      Collecting data...
                    </div>
                  </v-card>
                </template>
                <div v-else class="text-center grey--text pa-8">
                  No metrics available for this service
                </div>
              </v-card>
            </v-tab-item>
          </v-tabs-items>
        </v-card>

        <!-- No service selected state -->
        <v-card v-else class="d-flex align-center justify-center" height="400" elevation="2">
          <div class="text-center grey--text">
            <v-icon size="64" color="grey lighten-1">
              mdi-cursor-default-click
            </v-icon>
            <div class="text-h6 mt-4">
              Select a service
            </div>
            <div class="text-body-2">
              Choose a service from the list to view details
            </div>
          </div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import AnsiUp from 'ansi_up'
import { format } from 'date-fns'
import Vue from 'vue'

import message_manager, { MessageLevel } from '@/libs/message-manager'
import { OneMoreTime } from '@/one-more-time'
import settingsStore from '@/store/settings'
import {
  LogLine,
  MessageResponse,
  ServiceMetrics,
  ServicesResponse,
  ServiceState,
} from '@/types/service-manager'
import back_axios, { isBackendOffline } from '@/utils/api'

const API_URL = '/service-manager'
const ansi = new AnsiUp()
const METRICS_HISTORY_LENGTH = 60

export default Vue.extend({
  name: 'ServiceManagerView',

  data() {
    return {
      services: [] as ServiceState[],
      services_loaded: false,
      selected_service: null as ServiceState | null,
      selected_index: undefined as number | undefined,
      service_logs: [] as LogLine[],
      service_metrics: null as ServiceMetrics | null,
      metrics_history: [] as ServiceMetrics[],
      search: '',
      detail_tab: 0,
      log_lines: 100,
      log_stream: null as string | null,
      auto_scroll: true,
      logs_loading: false,
      action_loading: false,
      config_saving: false,
      config_form: {
        enabled: true,
        command: '' as string,
        restart: false,
        restart_delay_sec: 1.0,
        stop_timeout_sec: 10.0,
        limits: {
          cpu_cores: null as number | null,
          memory_mb: null as number | null,
          max_pids: null as number | null,
        },
      },
      log_line_options: [50, 100, 250, 500, 1000],
      stream_options: [
        { text: 'All', value: null },
        { text: 'stdout', value: 'stdout' },
        { text: 'stderr', value: 'stderr' },
      ],
      fetch_services_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_logs_task: new OneMoreTime({ delay: 3000, disposeWith: this }),
      fetch_metrics_task: new OneMoreTime({ delay: 2000, disposeWith: this }),
    }
  },

  computed: {
    sorted_services(): ServiceState[] {
      return [...this.services].sort((a, b) => a.name.localeCompare(b.name))
    },
    filtered_services(): ServiceState[] {
      if (!this.search) return this.sorted_services
      const searchLower = this.search.toLowerCase()
      return this.sorted_services.filter((s) => s.name.toLowerCase().includes(searchLower))
    },
    running_count(): number {
      return this.services.filter((s) => s.status === 'running').length
    },
    hasEnvironmentVariables(): boolean {
      const env = this.selected_service?.env
      return !!env && Object.keys(env).length > 0
    },
    hasConfigChanges(): boolean {
      if (!this.selected_service) return false
      const s = this.selected_service
      const f = this.config_form
      const originalCommand = s.command?.join(' ') ?? ''
      return f.enabled !== s.enabled
        || f.command !== '' && f.command !== originalCommand
        || f.restart !== s.restart
        || f.restart_delay_sec !== s.restart_delay_sec
        || f.stop_timeout_sec !== s.stop_timeout_sec
        || (f.limits.cpu_cores ?? 0) !== (s.limits?.cpu_cores ?? 0)
        || (f.limits.memory_mb ?? 0) !== (s.limits?.memory_mb ?? 0)
        || (f.limits.max_pids ?? 0) !== (s.limits?.max_pids ?? 0)
    },
    baseChartOptions(): Record<string, unknown> {
      return {
        chart: {
          animations: { enabled: true, dynamicAnimation: { speed: 300 } },
          toolbar: { show: false },
          sparkline: { enabled: false },
          zoom: { enabled: false },
        },
        theme: { mode: settingsStore.is_dark_theme ? 'dark' : 'light' },
        stroke: { curve: 'smooth', width: 2 },
        grid: { show: true, strokeDashArray: 4, padding: { left: 10, right: 10 } },
        xaxis: {
          type: 'datetime',
          labels: { show: true, datetimeUTC: false, format: 'HH:mm:ss' },
          axisBorder: { show: false },
          axisTicks: { show: false },
        },
        tooltip: {
          x: { format: 'HH:mm:ss' },
        },
        legend: { show: false },
      }
    },
    cpuChartOptions(): Record<string, unknown> {
      return {
        ...this.baseChartOptions,
        colors: ['#2196F3'],
        yaxis: {
          min: 0,
          max: (max: number) => Math.max(max * 1.2, 10),
          labels: { formatter: (val: number) => `${val.toFixed(0)}%` },
          title: { text: 'CPU %' },
        },
      }
    },
    cpuChartSeries(): { name: string; data: [number, number][] }[] {
      return [{
        name: 'CPU',
        data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.cpu_percent ?? 0]),
      }]
    },
    memoryChartOptions(): Record<string, unknown> {
      return {
        ...this.baseChartOptions,
        colors: ['#4CAF50', '#2196F3'],
        yaxis: {
          min: 0,
          labels: { formatter: (val: number) => `${val.toFixed(0)} MB` },
          title: { text: 'MB' },
        },
      }
    },
    memoryChartSeries(): { name: string; data: [number, number][] }[] {
      return [
        {
          name: 'RAM',
          data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.memory_mb ?? 0]),
        },
        {
          name: 'Swap',
          data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.swap_mb ?? 0]),
        },
      ]
    },
    ioChartOptions(): Record<string, unknown> {
      return {
        ...this.baseChartOptions,
        colors: ['#FF9800', '#9C27B0'],
        yaxis: {
          min: 0,
          labels: { formatter: (val: number) => `${val.toFixed(2)} MB/s` },
          title: { text: 'I/O Rate' },
        },
      }
    },
    ioChartSeries(): { name: string; data: [number, number][] }[] {
      return [
        {
          name: 'Read',
          data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.io_read_rate_mbps ?? 0]),
        },
        {
          name: 'Write',
          data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.io_write_rate_mbps ?? 0]),
        },
      ]
    },
    networkChartOptions(): Record<string, unknown> {
      return {
        ...this.baseChartOptions,
        colors: ['#00BCD4', '#E91E63'],
        yaxis: {
          min: 0,
          labels: { formatter: (val: number) => `${val.toFixed(2)} MB/s` },
          title: { text: 'Net Rate' },
        },
      }
    },
    networkChartSeries(): { name: string; data: [number, number][] }[] {
      return [
        {
          name: 'RX',
          data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.net_rx_rate_mbps ?? 0]),
        },
        {
          name: 'TX',
          data: this.metrics_history.map((m) => [new Date(m.timestamp).getTime(), m.net_tx_rate_mbps ?? 0]),
        },
      ]
    },
  },

  watch: {
    log_lines() {
      this.fetchLogs()
    },
    log_stream() {
      this.fetchLogs()
    },
    service_logs() {
      if (this.auto_scroll) {
        this.$nextTick(() => {
          const viewer = this.$refs.logViewer as HTMLElement | undefined
          if (viewer) {
            viewer.scrollTop = viewer.scrollHeight
          }
        })
      }
    },
  },

  mounted() {
    this.fetch_services_task.setAction(this.fetchServices)
  },

  methods: {
    formatDiskRate(read?: number, write?: number): string {
      const r = read ?? 0
      const w = write ?? 0
      if (r < 0.01 && w < 0.01) return '0'
      return `R ${r.toFixed(2)} / W ${w.toFixed(2)} MB/s`
    },

    formatNetRate(rx?: number, tx?: number): string {
      const rxVal = rx ?? 0
      const txVal = tx ?? 0
      if (rxVal < 0.01 && txVal < 0.01) return '0'
      return `RX ${rxVal.toFixed(2)} / TX ${txVal.toFixed(2)} MB/s`
    },

    async fetchServices(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${API_URL}/services`,
        timeout: 10000,
      })
        .then((response) => {
          const data = response.data as ServicesResponse
          this.services = data.services
          this.services_loaded = true
          if (this.selected_service) {
            const updated = this.services.find((s) => s.name === this.selected_service?.name)
            if (updated) {
              this.selected_service = updated
            }
          }
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          message_manager.emitMessage(MessageLevel.Error, `Failed to fetch services: ${error}`)
        })
    },

    selectService(service: ServiceState): void {
      this.selected_service = service
      this.service_logs = []
      this.service_metrics = null
      this.metrics_history = []
      this.populateConfigForm(service)
      this.fetchLogs()
      this.fetchMetrics()
      this.fetch_logs_task.setAction(this.fetchLogs)
      this.fetch_metrics_task.setAction(this.fetchMetrics)
    },

    populateConfigForm(service: ServiceState): void {
      this.config_form = {
        enabled: service.enabled,
        command: service.command?.join(' ') ?? '',
        restart: service.restart,
        restart_delay_sec: service.restart_delay_sec,
        stop_timeout_sec: service.stop_timeout_sec,
        limits: {
          cpu_cores: service.limits?.cpu_cores ?? null,
          memory_mb: service.limits?.memory_mb ?? null,
          max_pids: service.limits?.max_pids ?? null,
        },
      }
    },

    async fetchLogs(): Promise<void> {
      if (!this.selected_service) return
      this.logs_loading = true
      const params: Record<string, string | number> = { tail: this.log_lines }
      if (this.log_stream) {
        params.stream = this.log_stream
      }
      await back_axios({
        method: 'get',
        url: `${API_URL}/services/${this.selected_service.name}/logs`,
        params,
        timeout: 10000,
      })
        .then((response) => {
          this.service_logs = response.data.lines as LogLine[]
        })
        .catch(() => {
          // Silently handle log fetch errors
        })
        .finally(() => {
          this.logs_loading = false
        })
    },

    async fetchMetrics(): Promise<void> {
      if (!this.selected_service) return
      await back_axios({
        method: 'get',
        url: `${API_URL}/metrics/${this.selected_service.name}`,
        timeout: 10000,
      })
        .then((response) => {
          const metrics = response.data.metrics as ServiceMetrics | null
          this.service_metrics = metrics
          if (metrics) {
            this.metrics_history.push(metrics)
            if (this.metrics_history.length > METRICS_HISTORY_LENGTH) {
              this.metrics_history.shift()
            }
          }
        })
        .catch(() => {
          // Silently handle metrics fetch errors
        })
    },

    async startService(): Promise<void> {
      if (!this.selected_service) return
      this.action_loading = true
      await back_axios({
        method: 'post',
        url: `${API_URL}/services/${this.selected_service.name}/start`,
        timeout: 30000,
      })
        .then((response) => {
          const data = response.data as MessageResponse
          message_manager.emitMessage(MessageLevel.Success, data.message)
          this.fetchServices()
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          message_manager.emitMessage(MessageLevel.Error, `Failed to start service: ${error}`)
        })
        .finally(() => {
          this.action_loading = false
        })
    },

    async stopService(): Promise<void> {
      if (!this.selected_service) return
      this.action_loading = true
      await back_axios({
        method: 'post',
        url: `${API_URL}/services/${this.selected_service.name}/stop`,
        timeout: 30000,
      })
        .then((response) => {
          const data = response.data as MessageResponse
          message_manager.emitMessage(MessageLevel.Success, data.message)
          this.fetchServices()
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          message_manager.emitMessage(MessageLevel.Error, `Failed to stop service: ${error}`)
        })
        .finally(() => {
          this.action_loading = false
        })
    },

    async restartService(): Promise<void> {
      if (!this.selected_service) return
      this.action_loading = true
      await back_axios({
        method: 'post',
        url: `${API_URL}/services/${this.selected_service.name}/restart`,
        timeout: 30000,
      })
        .then((response) => {
          const data = response.data as MessageResponse
          message_manager.emitMessage(MessageLevel.Success, data.message)
          this.fetchServices()
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          message_manager.emitMessage(MessageLevel.Error, `Failed to restart service: ${error}`)
        })
        .finally(() => {
          this.action_loading = false
        })
    },

    async saveConfig(): Promise<void> {
      if (!this.selected_service) return
      this.config_saving = true
      const originalCommand = this.selected_service.command?.join(' ') ?? ''
      const body: Record<string, unknown> = {
        enabled: this.config_form.enabled,
        restart: this.config_form.restart,
        restart_delay_sec: this.config_form.restart_delay_sec,
        stop_timeout_sec: this.config_form.stop_timeout_sec,
        limits: {
          cpu_cores: this.config_form.limits.cpu_cores ?? 0,
          memory_mb: this.config_form.limits.memory_mb ?? 0,
          max_pids: this.config_form.limits.max_pids ?? 0,
        },
      }
      // Only send command if it's been changed
      if (this.config_form.command && this.config_form.command !== originalCommand) {
        body.command = this.config_form.command.split(/\s+/).filter((s: string) => s.length > 0)
      }
      await back_axios({
        method: 'patch',
        url: `${API_URL}/services/${this.selected_service.name}/config`,
        data: body,
        timeout: 10000,
      })
        .then((response) => {
          const data = response.data as MessageResponse
          message_manager.emitMessage(MessageLevel.Success, data.message)
          this.fetchServices()
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          message_manager.emitMessage(MessageLevel.Error, `Failed to save config: ${error}`)
        })
        .finally(() => {
          this.config_saving = false
        })
    },

    async resetServiceConfig(): Promise<void> {
      if (!this.selected_service) return
      await back_axios({
        method: 'post',
        url: `${API_URL}/services/${this.selected_service.name}/reset`,
        timeout: 10000,
      })
        .then((response) => {
          const data = response.data as MessageResponse
          message_manager.emitMessage(MessageLevel.Success, data.message)
          this.fetchServices()
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          message_manager.emitMessage(MessageLevel.Error, `Failed to reset config: ${error}`)
        })
    },

    formatTimestamp(timestamp: string): string {
      try {
        return format(new Date(timestamp), 'HH:mm:ss.SSS')
      } catch {
        return timestamp
      }
    },

    formatDateTime(datetime: string): string {
      try {
        return format(new Date(datetime), 'yyyy-MM-dd HH:mm:ss')
      } catch {
        return datetime
      }
    },

    formatUptime(seconds: number): string {
      const days = Math.floor(seconds / 86400)
      const hours = Math.floor(seconds % 86400 / 3600)
      const minutes = Math.floor(seconds % 3600 / 60)
      const secs = Math.floor(seconds % 60)
      const parts = []
      if (days > 0) parts.push(`${days}d`)
      if (hours > 0) parts.push(`${hours}h`)
      if (minutes > 0) parts.push(`${minutes}m`)
      parts.push(`${secs}s`)
      return parts.join(' ')
    },

    formatLogContent(line: string): string {
      return ansi.ansi_to_html(line)
    },
  },
})
</script>

<style scoped>
.service-manager {
  height: calc(100vh - 64px);
  overflow: hidden;
}

.service-list-card {
  height: calc(100vh - 100px);
}

.service-list {
  max-height: calc(100vh - 220px);
  overflow-y: auto;
}

.service-detail-card {
  height: calc(100vh - 100px);
  overflow: hidden;
}

.detail-tabs-content {
  height: calc(100vh - 200px);
  overflow: auto;
}

.log-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.log-viewer {
  flex: 1;
  overflow-y: auto;
  background-color: #1e1e1e;
  color: #d4d4d4;
  font-size: 12px;
  line-height: 1.4;
}

.font-mono {
  font-family: 'Fira Code', Monaco, Menlo, 'Ubuntu Mono', monospace;
}

.log-line {
  white-space: pre-wrap;
  word-break: break-all;
}

.log-timestamp {
  color: #6a9955;
  margin-right: 8px;
}

.log-stream {
  display: inline-block;
  width: 50px;
  margin-right: 8px;
  font-weight: bold;
}

.log-stream.stdout {
  color: #569cd6;
}

.log-stream.stderr {
  color: #f14c4c;
}

.log-content {
  color: #d4d4d4;
}

.stderr-line .log-content {
  color: #f14c4c;
}

.config-tab-content {
  overflow-y: auto;
}

.env-table td {
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.metrics-tab-content {
  overflow-y: auto;
}
</style>
