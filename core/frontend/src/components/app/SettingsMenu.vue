<template>
  <v-container
    id="settings-menu-button"
    class="d-flex justify-center"
  >
    <v-btn
      class="mr-2"
      icon
      large
      elevation="2"
      @click="showDialog(true)"
    >
      <v-icon>mdi-cog</v-icon>
    </v-btn>
    <v-dialog
      class="pa-2"
      width="fit-content"
      :value="show_dialog"
      @input="showDialog"
    >
      <v-card class="mx-auto pa-2 flex-column">
        <div
          v-if="operation_in_progress"
          class="card-loading-overlay"
        >
          <SpinningLogo
            size="150"
            :subtitle="operation_description"
          />
        </div>
        <div class="pt-2">
          <v-alert v-if="has_operation_error" type="error">
            {{ operation_error }}
          </v-alert>
          <v-divider />
        </div>
        <v-card>
          <v-card-title class="align-center">
            Settings
          </v-card-title>

          <v-container class="pa-2 align-center">
            <v-btn
              v-tooltip="'Restores BlueOS services to default configurations'"
              class="ma-2"
              @click="reset_settings"
            >
              <v-icon left>
                mdi-cog-refresh
              </v-icon>
              Reset Settings
            </v-btn>
          </v-container>

          <v-divider />

          <v-card-title class="align-center">
            System Log Files ({{ log_folder_size }})
          </v-card-title>

          <v-card-actions class="flex-row">
            <v-btn
              v-tooltip="'Download log for all services in BlueOS'"
              class="ma-2"
              @click="download_service_log_files"
            >
              <v-icon left>
                mdi-folder-download
              </v-icon>
              Download
            </v-btn>

            <v-btn
              v-tooltip="'Frees up space on the SD card'"
              class="ma-2"
              :disabled="disable_remove || deletion_in_progress"
              @click="remove_service_log_files"
            >
              <v-icon left>
                mdi-trash-can
              </v-icon>
              Remove
            </v-btn>
          </v-card-actions>

          <v-expand-transition>
            <div v-if="deletion_in_progress" class="pa-4">
              <v-progress-linear
                indeterminate
                color="primary"
              />
              <div class="mt-2">
                <div class="text-subtitle-2">
                  Deleting: {{ current_deletion_path }}
                </div>
                <div class="text-caption">
                  Size: {{ formatSize(current_deletion_size / 1024) }}
                </div>
                <div class="text-caption">
                  Total: {{ formatSize(current_deletion_total_size / 1024) }}
                </div>
                <div class="text-caption">
                  Status: {{ current_deletion_status }}
                </div>
              </div>
            </div>
          </v-expand-transition>

          <v-divider />

          <v-card-title class="align-center">
            MAVLink Log Files ({{ mavlink_log_folder_size }})
          </v-card-title>

          <v-card-actions class="flex-row">
            <v-btn
              v-tooltip="'Download logs from MAVLink'"
              class="ma-2"
              @click="download_mavlink_log_files"
            >
              <v-icon left>
                mdi-folder-download
              </v-icon>
              Download
            </v-btn>

            <v-btn
              v-tooltip="'Frees up space on the SD card deleting MAVLink logs'"
              class="ma-2"
              :disabled="disable_remove_mavlink"
              @click="remove_mavlink_log_files"
            >
              <v-icon left>
                mdi-trash-can
              </v-icon>
              Remove
            </v-btn>
          </v-card-actions>

          <v-divider />

          <v-card-title class="align-center">
            Run Vehicle Configuration Wizard
          </v-card-title>

          <v-card-actions class="flex-row">
            <v-btn
              v-tooltip="'Run Wizard'"
              class="ma-2"
              @click="enable_wizard"
            >
              <v-icon left>
                mdi-wizard-hat
              </v-icon>
              Enable
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-card>
    </v-dialog>
    <v-dialog
      width="380"
      :value="show_reset_dialog"
      @input="show_reset_dialog = false"
    >
      <v-card>
        <v-container class="pa-8">
          Restart the system to finish the settings reset.
        </v-container>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import axios, { CancelTokenSource } from 'axios'
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import filebrowser from '@/libs/filebrowser'
import Notifier from '@/libs/notifier'
import bag from '@/store/bag'
import { commander_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { prettifySize } from '@/utils/helper_functions'
import { parseStreamingResponse } from '@/utils/streaming'

const API_URL = '/commander/v1.0'

const notifier = new Notifier(commander_service)

export default Vue.extend({
  name: 'SettingsMenu',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      disable_remove: true,
      disable_remove_mavlink: true,
      log_folder_size: null as null | string,
      mavlink_log_folder_size: null as null | string,
      show_dialog: false,
      show_reset_dialog: false,
      operation_in_progress: false,
      operation_description: '',
      operation_error: undefined as undefined | string,
      deletion_in_progress: false,
      deletion_log_abort_controller: null as null | CancelTokenSource,
      current_deletion_path: '',
      current_deletion_size: 0,
      current_deletion_total_size: 0,
      current_deletion_status: '',
    }
  },
  computed: {
    has_operation_error(): boolean {
      return this.operation_error !== undefined
    },
  },
  watch: {
    show_dialog: {
      handler(val) {
        if (!val) {
          this.deletion_log_abort_controller?.cancel()
        }
      },
      immediate: true,
    },
  },
  async mounted() {
    await this.get_log_folder_size()
    await this.get_mavlink_log_folder_size()
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
      this.prepare_operation('Checking system log size...')
      await back_axios({
        url: `${API_URL}/services/check_log_folder_size`,
        method: 'get',
        timeout: 30000,
      })
        .then((response) => {
          const folder_data_bytes = response.data
          const one_hundred_MB = 100 * 2 ** 20
          this.disable_remove = folder_data_bytes < one_hundred_MB
          this.log_folder_size = this.formatSize(folder_data_bytes / 1024)
        })
        .catch((error) => {
          this.operation_error = String(error)
          notifier.pushBackError('GET_SERVICES_LOG_SIZE', error)
        })
      this.operation_in_progress = false
    },
    async get_mavlink_log_folder_size(): Promise<void> {
      this.prepare_operation('Checking MAVLink log size...')
      await back_axios({
        url: `${API_URL}/services/check_mavlink_log_folder_size`,
        method: 'get',
        timeout: 30000,
      })
        .then((response) => {
          const folder_data_bytes = response.data
          const one_hundred_MB = 100 * 2 ** 20
          this.disable_remove_mavlink = folder_data_bytes < one_hundred_MB
          this.mavlink_log_folder_size = this.formatSize(folder_data_bytes / 1024)
        })
        .catch((error) => {
          this.operation_error = String(error)
          notifier.pushBackError('GET_MAVLINK_LOG_SIZE', error)
        })
      this.operation_in_progress = false
    },
    async reset_settings(): Promise<void> {
      this.prepare_operation('Resetting settings...')

      await back_axios({
        url: `${API_URL}/settings/reset`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 10000,
      })
        .then(() => {
          this.show_reset_dialog = true
        })
        .catch((error) => {
          this.operation_error = String(error)
          notifier.pushBackError('RESET_SETTINGS_FAIL', error)
        })
      this.operation_in_progress = false
    },
    async remove_service_log_files(): Promise<void> {
      this.deletion_log_abort_controller = axios.CancelToken.source()
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
            let result = parseStreamingResponse(progressEvent.currentTarget.response)
            result = result.filter((fragment) => fragment.fragment !== -1)
            const last_fragment = result.last()
            const total_deleted = result
              .reduce((acc, fragment) => acc + (JSON.parse(fragment?.data ?? '{}')?.size ?? 0), 0)

            if (last_fragment?.data) {
              try {
                const info = JSON.parse(last_fragment.data)
                this.current_deletion_path = info.path.length > 30 ? `...${info.path.slice(-20)}` : info.path
                this.current_deletion_size = info.size
                this.current_deletion_total_size = total_deleted
                this.current_deletion_status = info.success ? 'Deleting..' : 'Failed to delete file..'
              } catch (e) {
                console.error('Error parsing deletion info:', e)
              }
            }
          },
          cancelToken: this.deletion_log_abort_controller?.token,
        })
      } catch (error) {
        this.operation_error = String(error)
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
      this.showDialog(false)
    },
    showDialog(state: boolean): void {
      this.show_dialog = state
    },
  },
})
</script>

<style scoped>
.card-loading-overlay {
  position: absolute;
  display: flex;
  justify-content: center;
  align-items: center;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  backdrop-filter: blur(2px);
  z-index: 9999 !important;
}
</style>
