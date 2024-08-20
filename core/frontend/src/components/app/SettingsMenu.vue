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
              :disabled="disable_remove"
              @click="remove_service_log_files"
            >
              <v-icon left>
                mdi-trash-can
              </v-icon>
              Remove
            </v-btn>
          </v-card-actions>

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
import Vue from 'vue'

import filebrowser from '@/libs/filebrowser'
import Notifier from '@/libs/notifier'
import bag from '@/store/bag'
import { commander_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { prettifySize } from '@/utils/helper_functions'

const API_URL = '/commander/v1.0'

const notifier = new Notifier(commander_service)

export default Vue.extend({
  name: 'SettingsMenu',
  data() {
    return {
      disable_remove: true,
      disable_remove_mavlink: true,
      log_folder_size: null as null | string,
      mavlink_log_folder_size: null as null | string,
      show_dialog: false,
      show_reset_dialog: false,
    }
  },
  async mounted() {
    await this.get_log_folder_size()
    await this.get_mavlink_log_folder_size()
  },
  methods: {
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
          this.disable_remove = folder_data_bytes < one_hundred_MB
          this.log_folder_size = prettifySize(folder_data_bytes / 1024)
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
          this.disable_remove_mavlink = folder_data_bytes < one_hundred_MB
          this.mavlink_log_folder_size = prettifySize(folder_data_bytes / 1024)
        })
        .catch((error) => {
          notifier.pushBackError('GET_MAVLINK_LOG_SIZE', error)
        })
    },
    async reset_settings(): Promise<void> {
      await back_axios({
        url: `${API_URL}/settings/reset`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 2000,
      })
        .then(() => {
          this.show_reset_dialog = true
        })
        .catch((error) => {
          notifier.pushBackError('RESET_SETTINGS_FAIL', error)
        })
    },
    async remove_service_log_files(): Promise<void> {
      await back_axios({
        url: `${API_URL}/services/remove_log`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 5000,
      })
        .then(() => {
          this.get_log_folder_size()
        })
        .catch((error) => {
          notifier.pushBackError('REMOVE_SERVICES_LOG_FAIL', error)
        })
      this.showDialog(false)
    },
    async remove_mavlink_log_files(): Promise<void> {
      await back_axios({
        url: `${API_URL}/services/remove_mavlink_log`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 5000,
      })
        .then(() => {
          this.get_mavlink_log_folder_size()
        })
        .catch((error) => {
          notifier.pushBackError('REMOVE_MAVLINK_LOG_FAIL', error)
        })
      this.showDialog(false)
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
