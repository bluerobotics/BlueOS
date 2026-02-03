<template>
  <v-card height="100%">
    <v-container fluid class="overflow-auto" style="height: 100%;">
      <v-row justify="center">
        <v-col cols="12" lg="10" xl="8">
          <div class="d-flex align-center mb-6 mt-4">
            <v-avatar color="primary" size="56" class="mr-4">
              <v-icon size="32" color="white">
                mdi-cog
              </v-icon>
            </v-avatar>
            <div>
              <h1 class="text-h5 font-weight-medium">
                Settings
              </h1>
              <p class="text-body-2 text--secondary mb-0">
                Configure BlueOS system preferences and manage data
              </p>
            </div>
          </div>

          <v-card class="mb-4" elevation="2">
            <v-card-title class="d-flex align-center">
              <v-avatar color="primary" size="36" class="mr-3">
                <v-icon color="white" size="20">
                  mdi-palette
                </v-icon>
              </v-avatar>
              <div>
                <div class="text-subtitle-1 font-weight-medium">
                  Appearance
                </div>
                <div class="text-caption text--secondary">
                  Customize how BlueOS looks
                </div>
              </div>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-card
                    class="theme-card h-100"
                    :class="{ 'selected-card': settings.is_dark_theme }"
                    outlined
                    @click="settings.is_dark_theme = true"
                  >
                    <v-card-text class="d-flex align-center pa-4">
                      <v-avatar color="grey darken-3" size="48" class="mr-4">
                        <v-icon color="white" size="24">
                          mdi-weather-night
                        </v-icon>
                      </v-avatar>
                      <div class="flex-grow-1">
                        <div class="text-subtitle-1 font-weight-medium">
                          Dark Theme
                        </div>
                        <div class="text-caption text--secondary">
                          Easier on the eyes in low-light environments
                        </div>
                      </div>
                      <v-icon v-if="settings.is_dark_theme" color="primary" size="24">
                        mdi-check-circle
                      </v-icon>
                    </v-card-text>
                  </v-card>
                </v-col>
                <v-col cols="12" md="6">
                  <v-card
                    class="theme-card h-100"
                    :class="{ 'selected-card': !settings.is_dark_theme }"
                    outlined
                    @click="settings.is_dark_theme = false"
                  >
                    <v-card-text class="d-flex align-center pa-4">
                      <v-avatar color="amber darken-1" size="48" class="mr-4">
                        <v-icon color="white" size="24">
                          mdi-white-balance-sunny
                        </v-icon>
                      </v-avatar>
                      <div class="flex-grow-1">
                        <div class="text-subtitle-1 font-weight-medium">
                          Light Theme
                        </div>
                        <div class="text-caption text--secondary">
                          Better visibility in bright environments
                        </div>
                      </div>
                      <v-icon v-if="!settings.is_dark_theme" color="primary" size="24">
                        mdi-check-circle
                      </v-icon>
                    </v-card-text>
                  </v-card>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card class="mb-4" elevation="2">
            <v-card-title class="d-flex align-center">
              <v-avatar color="deep-purple" size="36" class="mr-3">
                <v-icon color="white" size="20">
                  mdi-tune
                </v-icon>
              </v-avatar>
              <div>
                <div class="text-subtitle-1 font-weight-medium">
                  Advanced Mode
                </div>
                <div class="text-caption text--secondary">
                  Access advanced features and hidden pages
                </div>
              </div>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row align="center" no-gutters class="mb-4">
                <v-col cols="12" sm="8">
                  <div class="d-flex align-center">
                    <v-avatar
                      :color="settings.is_pirate_mode ? 'error' : 'grey'"
                      size="48"
                      class="mr-4"
                    >
                      <v-icon color="white" size="28">
                        {{ settings.is_pirate_mode ? 'mdi-skull-crossbones' : 'mdi-robot-happy' }}
                      </v-icon>
                    </v-avatar>
                    <div>
                      <div class="text-subtitle-1 font-weight-medium">
                        Pirate Mode
                      </div>
                      <div class="text-caption text--secondary">
                        {{ settings.is_pirate_mode
                          ? 'Enabled - Advanced features are visible'
                          : 'Show hidden pages and advanced settings'
                        }}
                      </div>
                    </div>
                  </div>
                </v-col>
                <v-col cols="12" sm="4" class="text-sm-right mt-3 mt-sm-0">
                  <v-switch
                    v-model="settings.is_pirate_mode"
                    inset
                    hide-details
                    :label="settings.is_pirate_mode ? 'Enabled' : 'Disabled'"
                    class="mt-0 pt-0 d-inline-flex"
                  />
                </v-col>
              </v-row>

              <v-expand-transition>
                <v-row v-if="settings.is_pirate_mode" align="center" no-gutters>
                  <v-col cols="12" sm="8">
                    <div class="d-flex align-center">
                      <v-avatar
                        :color="settings.is_dev_mode ? 'primary' : 'grey'"
                        size="48"
                        class="mr-4"
                      >
                        <v-icon color="white" size="28">
                          mdi-code-braces
                        </v-icon>
                      </v-avatar>
                      <div>
                        <div class="text-subtitle-1 font-weight-medium">
                          Developer Mode
                        </div>
                        <div class="text-caption text--secondary">
                          {{ settings.is_dev_mode
                            ? 'Enabled - Development tools are active'
                            : 'Enable additional debugging and development tools'
                          }}
                        </div>
                      </div>
                    </div>
                  </v-col>
                  <v-col cols="12" sm="4" class="text-sm-right mt-3 mt-sm-0">
                    <v-switch
                      v-model="settings.is_dev_mode"
                      inset
                      hide-details
                      :label="settings.is_dev_mode ? 'Enabled' : 'Disabled'"
                      class="mt-0 pt-0 d-inline-flex"
                    />
                  </v-col>
                </v-row>
              </v-expand-transition>
            </v-card-text>
          </v-card>

          <v-card class="mb-4" elevation="2">
            <v-card-title class="d-flex align-center">
              <v-avatar color="info" size="36" class="mr-3">
                <v-icon color="white" size="20">
                  mdi-database-cog
                </v-icon>
              </v-avatar>
              <div>
                <div class="text-subtitle-1 font-weight-medium">
                  Data Management
                </div>
                <div class="text-caption text--secondary">
                  Manage logs and system data
                </div>
              </div>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row align="center" no-gutters class="mb-4">
                <v-col cols="12" sm="6">
                  <div class="d-flex align-center">
                    <v-avatar color="info" size="48" class="mr-4">
                      <v-icon color="white" size="28">
                        mdi-file-document-multiple
                      </v-icon>
                    </v-avatar>
                    <div>
                      <div class="text-subtitle-1 font-weight-medium">
                        System Logs
                      </div>
                      <div class="text-caption text--secondary">
                        BlueOS service logs
                        <v-chip
                          v-if="log_folder_size"
                          x-small
                          class="ml-2"
                          :color="log_size_warning ? 'warning' : 'grey'"
                        >
                          {{ log_folder_size }}
                        </v-chip>
                      </div>
                    </div>
                  </div>
                </v-col>
                <v-col cols="12" sm="6" class="text-sm-right mt-3 mt-sm-0">
                  <v-btn
                    v-tooltip="'Download logs for all BlueOS services'"
                    class="mr-2"
                    outlined
                    small
                    @click="download_service_log_files"
                  >
                    <v-icon left small>
                      mdi-download
                    </v-icon>
                    Download
                  </v-btn>
                  <v-btn
                    v-tooltip="'Free up space by removing old logs'"
                    outlined
                    small
                    :disabled="disable_remove || deletion_in_progress"
                    color="error"
                    @click="remove_service_log_files"
                  >
                    <v-icon left small>
                      mdi-trash-can
                    </v-icon>
                    Clear
                  </v-btn>
                </v-col>
              </v-row>

              <v-expand-transition>
                <div v-if="deletion_in_progress" class="mb-4">
                  <v-progress-linear indeterminate color="primary" class="mb-2" />
                  <div class="text-caption">
                    <strong>Deleting:</strong> {{ current_deletion_path }}
                  </div>
                  <div class="text-caption text--secondary">
                    Freed: {{ formatSize(current_deletion_total_size / 1024) }}
                  </div>
                </div>
              </v-expand-transition>

              <v-divider class="my-4" />

              <v-row align="center" no-gutters>
                <v-col cols="12" sm="6">
                  <div class="d-flex align-center">
                    <v-avatar color="success" size="48" class="mr-4">
                      <v-icon color="white" size="28">
                        mdi-airplane
                      </v-icon>
                    </v-avatar>
                    <div>
                      <div class="text-subtitle-1 font-weight-medium">
                        MAVLink Logs
                      </div>
                      <div class="text-caption text--secondary">
                        Autopilot flight logs
                        <v-chip
                          v-if="mavlink_log_folder_size"
                          x-small
                          class="ml-2"
                          :color="mavlink_size_warning ? 'warning' : 'grey'"
                        >
                          {{ mavlink_log_folder_size }}
                        </v-chip>
                      </div>
                    </div>
                  </div>
                </v-col>
                <v-col cols="12" sm="6" class="text-sm-right mt-3 mt-sm-0">
                  <v-btn
                    v-tooltip="'Download MAVLink logs'"
                    class="mr-2"
                    outlined
                    small
                    @click="download_mavlink_log_files"
                  >
                    <v-icon left small>
                      mdi-download
                    </v-icon>
                    Download
                  </v-btn>
                  <v-btn
                    v-tooltip="'Free up space by removing MAVLink logs'"
                    outlined
                    small
                    :disabled="disable_remove_mavlink"
                    color="error"
                    @click="remove_mavlink_log_files"
                  >
                    <v-icon left small>
                      mdi-trash-can
                    </v-icon>
                    Clear
                  </v-btn>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>

          <v-card class="mb-4" elevation="2">
            <v-card-title class="d-flex align-center">
              <v-avatar color="warning" size="36" class="mr-3">
                <v-icon color="white" size="20">
                  mdi-wrench
                </v-icon>
              </v-avatar>
              <div>
                <div class="text-subtitle-1 font-weight-medium">
                  System
                </div>
                <div class="text-caption text--secondary">
                  System configuration and maintenance
                </div>
              </div>
            </v-card-title>
            <v-divider />
            <v-card-text>
              <v-row>
                <v-col cols="12" md="6">
                  <v-row align="center" no-gutters>
                    <v-col cols="12" sm="8">
                      <div class="d-flex align-center">
                        <v-avatar color="warning" size="48" class="mr-4">
                          <v-icon color="white" size="28">
                            mdi-wizard-hat
                          </v-icon>
                        </v-avatar>
                        <div>
                          <div class="text-subtitle-1 font-weight-medium">
                            Configuration Wizard
                          </div>
                          <div class="text-caption text--secondary">
                            Re-run the initial vehicle setup wizard
                          </div>
                        </div>
                      </div>
                    </v-col>
                    <v-col cols="12" class="mt-3">
                      <v-btn
                        v-tooltip="'Start the configuration wizard'"
                        outlined
                        @click="enable_wizard"
                      >
                        <v-icon left>
                          mdi-wizard-hat
                        </v-icon>
                        Run Wizard
                      </v-btn>
                    </v-col>
                  </v-row>
                </v-col>
                <v-col cols="12" md="6">
                  <v-row align="center" no-gutters>
                    <v-col cols="12" sm="8">
                      <div class="d-flex align-center">
                        <v-avatar color="error" size="48" class="mr-4">
                          <v-icon color="white" size="28">
                            mdi-cog-refresh
                          </v-icon>
                        </v-avatar>
                        <div>
                          <div class="text-subtitle-1 font-weight-medium">
                            Reset Settings
                          </div>
                          <div class="text-caption text--secondary">
                            Restore all BlueOS services to defaults
                          </div>
                        </div>
                      </div>
                    </v-col>
                    <v-col cols="12" class="mt-3">
                      <v-btn
                        v-tooltip="'Reset all BlueOS settings to factory defaults'"
                        outlined
                        color="error"
                        @click="confirm_reset_settings"
                      >
                        <v-icon left>
                          mdi-cog-refresh
                        </v-icon>
                        Reset Settings
                      </v-btn>
                    </v-col>
                  </v-row>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <v-overlay :value="operation_in_progress" z-index="1000">
        <div class="text-center">
          <spinning-logo size="120" :subtitle="operation_description" />
        </div>
      </v-overlay>

      <v-snackbar
        v-model="show_error"
        color="error"
        timeout="5000"
        top
      >
        {{ operation_error }}
        <template #action="{ attrs }">
          <v-btn text v-bind="attrs" @click="show_error = false">
            Close
          </v-btn>
        </template>
      </v-snackbar>

      <warning-dialog
        v-model="show_reset_warning"
        :message="resetWarningMessage"
        confirm-label="Yes, reset settings"
        @confirm="onConfirmResetSettings"
      />

      <v-dialog width="400" :value="show_reset_dialog" @input="show_reset_dialog = false">
        <v-card>
          <v-card-title class="text-h6">
            <v-icon left color="success">
              mdi-check-circle
            </v-icon>
            Settings Reset Complete
          </v-card-title>
          <v-card-text>
            Restart the system to finish the settings reset.
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" text @click="show_reset_dialog = false">
              Close
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>
    </v-container>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import WarningDialog from '@/components/common/WarningDialog.vue'
import filebrowser from '@/libs/filebrowser'
import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import { OneMoreTime } from '@/one-more-time'
import bag from '@/store/bag'
import { commander_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { prettifySize } from '@/utils/helper_functions'
import { parseStreamingResponse } from '@/utils/streaming'

const API_URL = '/commander/v1.0'
const notifier = new Notifier(commander_service)

export default Vue.extend({
  name: 'SettingsView',

  components: {
    SpinningLogo,
    WarningDialog,
  },

  data() {
    return {
      settings,
      disable_remove: true,
      disable_remove_mavlink: true,
      log_folder_size: null as null | string,
      mavlink_log_folder_size: null as null | string,
      show_reset_dialog: false,
      show_reset_warning: false,
      show_error: false,
      operation_in_progress: false,
      operation_description: '',
      operation_error: undefined as undefined | string,
      deletion_in_progress: false,
      deletion_log_abort_controller: null as null | AbortController,
      current_deletion_path: '',
      current_deletion_size: 0,
      current_deletion_total_size: 0,
      current_deletion_status: '',
      log_size_bytes: 0,
      mavlink_size_bytes: 0,
      fetch_task: new OneMoreTime({ delay: 30000, disposeWith: this }),
    }
  },

  computed: {
    resetWarningMessage(): string {
      return (
        'Resetting will restore BlueOS services to their default configurations.\n'
        + 'This action cannot be undone. Proceed?'
      )
    },
    log_size_warning(): boolean {
      const one_hundred_MB = 100 * 2 ** 20
      return this.log_size_bytes >= one_hundred_MB
    },
    mavlink_size_warning(): boolean {
      const one_hundred_MB = 100 * 2 ** 20
      return this.mavlink_size_bytes >= one_hundred_MB
    },
  },

  mounted() {
    this.fetch_task.setAction(async () => {
      await this.get_log_folder_size()
      await this.get_mavlink_log_folder_size()
    })
  },

  methods: {
    prepare_operation(description: string): void {
      this.operation_error = undefined
      this.operation_in_progress = true
      this.operation_description = description
    },

    formatSize(bytes: number): string {
      return prettifySize(bytes)
    },

    async download_service_log_files(): Promise<void> {
      const folder = await filebrowser.fetchFolder('system_logs')
      await filebrowser.downloadFolder(folder)
    },

    async download_mavlink_log_files(): Promise<void> {
      const folder = await filebrowser.fetchFolder('ardupilot_logs/logs')
      await filebrowser.downloadFolder(folder)
    },

    async get_log_folder_size(): Promise<void> {
      await back_axios({
        url: `${API_URL}/services/check_log_folder_size`,
        method: 'get',
        timeout: 30000,
      })
        .then((response) => {
          const folder_data_bytes = response.data
          const one_hundred_MB = 100 * 2 ** 20
          this.log_size_bytes = folder_data_bytes
          this.disable_remove = folder_data_bytes < one_hundred_MB
          this.log_folder_size = this.formatSize(folder_data_bytes / 1024)
        })
        .catch((error) => {
          notifier.pushBackError('GET_SERVICES_LOG_SIZE', error)
        })
    },

    async get_mavlink_log_folder_size(): Promise<void> {
      await back_axios({
        url: `${API_URL}/services/check_mavlink_log_folder_size`,
        method: 'get',
        timeout: 30000,
      })
        .then((response) => {
          const folder_data_bytes = response.data
          const one_hundred_MB = 100 * 2 ** 20
          this.mavlink_size_bytes = folder_data_bytes
          this.disable_remove_mavlink = folder_data_bytes < one_hundred_MB
          this.mavlink_log_folder_size = this.formatSize(folder_data_bytes / 1024)
        })
        .catch((error) => {
          notifier.pushBackError('GET_MAVLINK_LOG_SIZE', error)
        })
    },

    confirm_reset_settings(): void {
      this.show_reset_warning = true
    },

    onConfirmResetSettings(): void {
      this.show_reset_warning = false
      this.reset_settings()
    },

    async reset_settings(): Promise<void> {
      this.prepare_operation('Resetting settings...')

      await back_axios({
        url: `${API_URL}/settings/reset`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 30000,
      })
        .then(() => {
          this.show_reset_dialog = true
        })
        .catch((error) => {
          this.operation_error = String(error)
          this.show_error = true
          notifier.pushBackError('RESET_SETTINGS_FAIL', error)
        })
      this.operation_in_progress = false
    },

    async remove_service_log_files(): Promise<void> {
      this.deletion_log_abort_controller = new AbortController()
      this.deletion_in_progress = true
      this.current_deletion_path = '...'
      this.current_deletion_size = 0
      this.current_deletion_total_size = 0
      this.current_deletion_status = 'Starting deletion...'

      try {
        await back_axios({
          url: `${API_URL}/services/remove_log_stream`,
          method: 'post',
          params: {
            i_know_what_i_am_doing: true,
          },
          responseType: 'text',
          onDownloadProgress: (progressEvent) => {
            let result = parseStreamingResponse(progressEvent.event.currentTarget.response)
            result = result.filter((fragment) => fragment.fragment !== -1)
            const last_fragment = result.last()
            const total_deleted = result
              .reduce((acc, fragment) => acc + (JSON.parse(fragment?.data ?? '{}')?.size ?? 0), 0)

            if (last_fragment?.data) {
              try {
                const info = JSON.parse(last_fragment.data)
                this.current_deletion_path = info.path.length > 40 ? `...${info.path.slice(-35)}` : info.path
                this.current_deletion_size = info.size
                this.current_deletion_total_size = total_deleted
                this.current_deletion_status = info.success ? 'Deleting..' : 'Failed to delete file..'
              } catch (e) {
                console.error('Error parsing deletion info:', e)
              }
            }
          },
          signal: this.deletion_log_abort_controller?.signal,
        })
      } catch (error) {
        this.operation_error = String(error)
        this.show_error = true
        notifier.pushBackError('REMOVE_SERVICES_LOG_FAIL', error)
      } finally {
        this.operation_in_progress = false
        this.deletion_in_progress = false
        this.current_deletion_path = ''
        this.current_deletion_size = 0
        this.current_deletion_status = ''
      }

      this.get_log_folder_size()
    },

    async remove_mavlink_log_files(): Promise<void> {
      this.prepare_operation('Removing MAVLink log files...')

      await back_axios({
        url: `${API_URL}/services/remove_mavlink_log`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 20000,
      })
        .then(() => {
          this.get_mavlink_log_folder_size()
        })
        .catch((error) => {
          this.operation_error = String(error)
          this.show_error = true
          notifier.pushBackError('REMOVE_MAVLINK_LOG_FAIL', error)
        })
      this.operation_in_progress = false
    },

    async enable_wizard(): Promise<void> {
      const payload = { version: 0 }
      await bag.setData('wizard', payload)
        .then((result) => {
          if (result) {
            this.$router.push('/')
            window.location.reload()
          }
        })
        .catch(() => {
          notifier.pushBackError('ENABLE_WIZARD', 'Failed to enable wizard')
        })
    },
  },
})
</script>

<style scoped>
.theme-card {
  transition: all 0.2s ease;
  cursor: pointer;
}

.theme-card:hover {
  border-color: var(--v-primary-base) !important;
}

.theme-card.selected-card {
  border-color: var(--v-primary-base) !important;
  border-width: 2px;
}

.h-100 {
  height: 100%;
}
</style>
