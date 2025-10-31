<template>
  <v-card
    elevation="0"
    class="pa-2"
  >
    <v-alert
      v-if="only_bootloader_boards_available"
      type="warning"
      class="mb-6"
      icon="mdi-information-outline"
      text
    >
      <div class="d-flex flex-column">
        <p class="mr-2" style="text-align: justify;">
          <strong>  Only bootloader boards detected.</strong> This likely means the firmware is corrupted.
          Please select the correct vehicle type and update to the latest autopilot firmware.
        </p>
        <p class="mr-2" style="text-align: justify;">
          <strong>Installation may take a few minutes.</strong>
        </p>
        <div
          v-if="has_install_failed"
          class="bl-only-info-action"
        >
          <p class="mr-2 mb-0" style="text-align: justify;">
            If it fails, this is normal for some corrupted firmware. Just reboot the onboard computer and try again from
            this page.
          </p>
          <v-btn
            v-tooltip="'Fully restarts the onboard computer'"
            class="ma-2"
            @click="rebootOnBoardComputer"
          >
            <v-icon
              left
              color="orange"
            >
              mdi-restart-alert
            </v-icon>
            Reboot
          </v-btn>
        </div>
      </div>
    </v-alert>
    <div id="update-configs">
      <div id="update-modes">
        <v-item-group
          v-model="upload_type"
          mandatory
          class="ma-2 d-flex align-center justify-center flex-wrap"
        >
          <v-item
            v-slot="{ active, toggle }"
            :value="UploadType.Cloud"
          >
            <v-btn
              block
              small
              width="180"
              :color="active ? 'accent' : ''"
              class="ma-1"
              @click="toggle"
            >
              <v-icon class="mr-2">
                mdi-cloud-arrow-down
              </v-icon>
              <div>Retrieve from Cloud</div>
            </v-btn>
          </v-item>
          <v-item
            v-slot="{ active, toggle }"
            :value="UploadType.File"
          >
            <v-btn
              block
              small
              width="180"
              :color="active ? 'accent' : ''"
              class="ma-1"
              @click="toggle"
            >
              <v-icon class="mr-2">
                mdi-upload
              </v-icon>
              <div>Upload firmware file</div>
            </v-btn>
          </v-item>
          <v-item
            v-slot="{ active, toggle }"
            :value="UploadType.Restore"
          >
            <v-btn
              block
              small
              width="180"
              :color="active ? 'accent' : ''"
              class="ma-1"
              @click="toggle"
            >
              <v-icon class="mr-2">
                mdi-file-restore
              </v-icon>
              <div>Restore default firmware</div>
            </v-btn>
          </v-item>
        </v-item-group>
      </div>
      <div id="update-options">
        <v-select
          v-if="settings.is_pirate_mode || only_bootloader_boards_available"
          v-model="chosen_board"
          :items="available_boards"
          label="Board"
          hint="If no board is chosen the system will try to flash the currently running board."
          class="ma-1 pa-0"
          @change="clearFirmwareSelection()"
        />
        <div
          v-if="upload_type === UploadType.Cloud"
        >
          <v-select
            v-model="chosen_vehicle"
            :items="vehicle_types"
            label="Vehicle type"
            required
            class="ma-1 pa-0"
            @change="updateAvailableFirmwares"
          />
          <v-select
            v-if="platforms_available.length > 1"
            v-model="chosen_platform"
            class="ma-1 pa-0"
            :disabled="disable_firmware_selection"
            :items="platforms_available"
            :label="platform_selector_label"
            :loading="loading_firmware_options"
            required
          />
          <div class="d-flex">
            <v-select
              v-model="chosen_firmware_url"
              class="ma-1 pa-0"
              :disabled="disable_firmware_selection"
              :items="showable_firmware_deduplicated"
              :label="firmware_selector_label"
              :loading="loading_firmware_options"
              required
              @change="setCloudFirmwareChosen"
            />
            <v-tooltip bottom>
              <template #activator="{ on, attrs }">
                <v-icon
                  class="ml-4"
                  v-bind="attrs"
                  v-on="on"
                >
                  mdi-information
                </v-icon>
              </template>
              <p>Stable - A production-ready release. Suitable for most users.</p>
              <p>Beta - In-testing, with new features and improvements, aiming to become stable. May have bugs.</p>
              <p>
                Dev - Development branch, with all the newest features.
                Intentionally unstable (changes quickly), and possibly untested/dangerous.
              </p>
            </v-tooltip>
          </div>
        </div>

        <v-file-input
          v-if="upload_type === UploadType.File"
          class="mr-2"
          show-size
          label="Firmware file"
          @change="setFileFirmware"
        />

        <p
          v-if="upload_type === UploadType.Restore"
        >
          This option will restore the default firmware for your platform.
        </p>
      </div>
    </div>
    <v-btn
      :disabled="!allow_installing"
      class="mt-6"
      color="primary"
      @click="installFirmware"
    >
      <v-icon class="mr-2">
        mdi-content-save
      </v-icon>
      <div>Install firmware</div>
    </v-btn>

    <v-dialog
      v-model="show_install_progress"
      hide-overlay
      persistent
      width="600"
    >
      <v-card
        color="primary"
        dark
      >
        <v-card-title>
          Installing firmware
        </v-card-title>
        <v-card-text>
          <v-progress-linear
            indeterminate
            color="white"
            class="mb-4"
          />
          <div
            v-if="install_logs.length > 0"
            class="install-logs pa-2"
          >
            <div
              v-for="(log, index) in install_logs"
              :key="index"
              :class="{ 'error-log': log.stream === 'stderr', 'info-log': log.stream === 'stdout' }"
              class="log-line"
            >
              {{ log.data.replace(/\r/g, '\n') }}<br>
            </div>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-alert
      v-model="show_install_alert"
      dismissible
      :color="install_alert_color"
      border="left"
      elevation="2"
      colored-border
      :icon="install_alert_icon"
      class="ma-6"
    >
      <p>{{ install_result_message }}</p>
    </v-alert>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import commander from '@/store/commander'
import {
  Firmware,
  FlightController,
  FlightControllerFlags,
  Vehicle,
} from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

enum InstallStatus {
  NotStarted,
  Installing,
  Succeeded,
  Failed
}

enum CloudFirmwareOptionsStatus {
  NotFetched,
  Fetching,
  FetchSucceeded,
  FetchFailed,
  Chosen
}

enum UploadType {
  Cloud,
  File,
  Restore
}

export default Vue.extend({
  name: 'FirmwareManager',
  data() {
    const { current_board } = autopilot
    const { rebootOnBoardComputer, requestOnBoardComputerReboot } = commander
    return {
      settings,
      cloud_firmware_options_status: CloudFirmwareOptionsStatus.NotFetched,
      install_status: InstallStatus.NotStarted,
      UploadType,
      upload_type: UploadType.Cloud,
      chosen_board: current_board as (FlightController | null),
      chosen_vehicle: null as (Vehicle | null),
      chosen_firmware_url: null as (URL | null),
      available_firmwares: [] as Firmware[],
      firmware_file: null as (Blob | null),
      install_result_message: '',
      chosen_platform: null as (string | null),
      install_logs: [] as Array<{stream: string, data: string}>,
      rebootOnBoardComputer,
      requestOnBoardComputerReboot,
    }
  },
  computed: {
    platforms_available(): string[] {
      return Array.from(new Set(this.available_firmwares.map((firmware) => firmware.platform)))
    },
    platform_selector_label(): string {
      return this.loading_firmware_options ? 'Fetching available platforms...' : 'Platform'
    },
    firmware_selector_label(): string {
      return this.loading_firmware_options ? 'Fetching available firmware...' : 'Firmware'
    },
    loading_firmware_options(): boolean {
      return this.cloud_firmware_options_status === CloudFirmwareOptionsStatus.Fetching
    },
    show_install_progress(): boolean {
      return this.install_status === InstallStatus.Installing
    },
    show_install_alert(): boolean {
      return [InstallStatus.Succeeded, InstallStatus.Failed].includes(this.install_status)
    },
    install_alert_color(): string {
      return this.install_status === InstallStatus.Succeeded ? 'teal' : 'red'
    },
    install_alert_icon(): string {
      return this.install_status === InstallStatus.Succeeded ? 'mdi-check-decagram' : 'close-octagon'
    },
    has_install_failed(): boolean {
      return this.install_status === InstallStatus.Failed
    },
    vehicle_types(): {value: string, text: Vehicle}[] {
      return Object.entries(Vehicle).map(
        (vehicle) => ({ value: vehicle[0], text: vehicle[1] }),
      )
    },
    no_sitl_boards(): FlightController[] {
      return autopilot.available_boards.filter((board) => board.name.toLowerCase() !== 'sitl')
    },
    only_bootloader_boards_available(): boolean {
      /** If user explicitly selected SITL, we don't want to show as bootloader only boards */
      if (autopilot.current_board?.name.toLowerCase() === 'sitl') {
        return false
      }

      return this.no_sitl_boards.length > 0
        && this.no_sitl_boards.every((board) => board.flags.includes(FlightControllerFlags.is_bootloader))
    },
    available_boards(): {value: FlightController, text: string}[] {
      return (this.only_bootloader_boards_available ? this.no_sitl_boards : autopilot.available_boards).map(
        (board) => ({
          value: board,
          text: board.name === autopilot.current_board?.name ? `${board.name} (current)` : board.name,
        }),
      )
    },
    disable_firmware_selection(): boolean {
      return this.chosen_vehicle == null || this.loading_firmware_options
    },
    showable_firmwares(): {value: URL, text: string}[] {
      return this.available_firmwares.filter(
        (firmware) => firmware.platform === this.chosen_platform,
      ).map((firmware) => ({ value: firmware.url, text: firmware.name }))
        .filter((firmware) => firmware.text !== 'OFFICIAL')
        .sort((a, b) => {
          const release_show_order = ['dev', 'beta', 'stable']
          const prior_a = release_show_order.indexOf(a.text.toLowerCase().split('-')[0])
          const prior_b = release_show_order.indexOf(b.text.toLowerCase().split('-')[0])
          return prior_a > prior_b ? 1 : -1
        })
        .reverse()
    },
    showable_firmware_deduplicated(): {value: URL, text: string}[] {
      // qdd the trailing filename from the url to the value of an entry if another entry has the same text
      return this.showable_firmwares.map((firmware) => {
        const same_text_entries = this.showable_firmwares.filter((f) => f.text === firmware.text)
        if (same_text_entries.length > 1) {
          return { value: firmware.value, text: `${firmware.text} (${firmware.value.toString().split('/').pop()})` }
        }
        return firmware
      })
    },
    allow_installing(): boolean {
      if (this.install_status === InstallStatus.Installing) {
        return false
      }
      if (this.upload_type === UploadType.Cloud) {
        return this.cloud_firmware_options_status === CloudFirmwareOptionsStatus.Chosen
      }
      if (this.upload_type === UploadType.File) {
        return this.firmware_file != null
      }
      return true
    },
  },
  watch: {
    only_bootloader_boards_available(new_value: boolean): void {
      if (new_value) {
        this.setFirstNoSitlBoard()
      }
    },
    has_install_failed(new_value: boolean): void {
      if (new_value && this.only_bootloader_boards_available) {
        this.requestOnBoardComputerReboot()
      }
    },
    platforms_available(new_value: string[]): void {
      if (new_value.length === 1) {
        const [chosen_platform] = new_value
        this.chosen_platform = chosen_platform
      }
    },
  },
  mounted(): void {
    if (this.only_bootloader_boards_available) {
      this.setFirstNoSitlBoard()
    }
  },
  methods: {
    clearFirmwareSelection(): void {
      this.chosen_firmware_url = null
      this.chosen_platform = null
      this.available_firmwares = []
    },
    setFirstNoSitlBoard(): void {
      const [first_board] = this.no_sitl_boards
      this.chosen_board = first_board
    },
    async updateAvailableFirmwares(): Promise<void> {
      this.chosen_firmware_url = null
      this.chosen_platform = null
      this.available_firmwares = []
      this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.Fetching
      await back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/available_firmwares`,
        timeout: 30000,
        params: { vehicle: this.chosen_vehicle, board_name: this.chosen_board?.platform.name },
      })
        .then((response) => {
          this.available_firmwares = response.data
          this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.FetchSucceeded
        })
        .catch((error) => {
          this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.FetchFailed
          notifier.pushError('FIRMWARE_FETCH_FAIL', error)
        })
    },
    setCloudFirmwareChosen(): void {
      this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.Chosen
    },
    setFileFirmware(file: (Blob | null)): void {
      this.firmware_file = file
    },
    async installFirmware(): Promise<void> {
      this.install_status = InstallStatus.Installing
      this.install_logs = []

      let url = ''
      let requestOptions: RequestInit = {
        method: 'POST',
      }

      if (this.upload_type === UploadType.Cloud) {
        // Populate request with data for cloud install
        const params = new URLSearchParams({
          url: this.chosen_firmware_url?.toString() ?? '',
          board_name: this.chosen_board?.platform.name ?? '',
        })
        url = `${autopilot.API_URL}/install_firmware_from_url?${params}`
      } else if (this.upload_type === UploadType.Restore) {
        // Populate request with data for restore install
        const params = new URLSearchParams({
          board_name: this.chosen_board?.platform.name ?? '',
        })
        url = `${autopilot.API_URL}/restore_default_firmware?${params}`
      } else {
        // Populate request with data for file install
        if (!this.firmware_file) {
          const message = 'Could not upload firmware: no firmware file selected.'
          notifier.pushWarning('FILE_FIRMWARE_UPLOAD_FAIL', message)
          return
        }
        const form_data = new FormData()
        form_data.append('binary', this.firmware_file)
        const params = new URLSearchParams({
          board_name: this.chosen_board?.platform.name ?? '',
        })
        url = `${autopilot.API_URL}/install_firmware_from_file?${params}`
        requestOptions = {
          method: 'POST',
          body: form_data,
        }
      }

      try {
        const response = await fetch(url, requestOptions)

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }

        const reader = response.body?.getReader()
        const decoder = new TextDecoder()

        if (!reader) {
          throw new Error('No response body')
        }

        let buffer = ''

        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read()

          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')

          // Keep the last incomplete line in the buffer
          buffer = lines.pop() ?? ''

          // Process complete lines
          for (const line of lines) {
            if (line.trim()) {
              try {
                const log = JSON.parse(line)

                // Check if backend sent "done" signal to close connection
                if (log.stream === 'done') {
                  // Close the progress dialog immediately
                  this.install_status = InstallStatus.Succeeded
                  this.install_result_message = 'Installation completed'
                  return
                }

                this.install_logs.push(log)
              } catch (e) {
                console.error('Failed to parse log line:', line, e)
              }
            }
          }
        }

        // Check if there were any error messages in the logs
        const hasErrors = this.install_logs.some((log) => log.stream === 'stderr')

        if (hasErrors) {
          this.install_status = InstallStatus.Failed
          // Get the last error message
          const lastError = this.install_logs
            .filter((log) => log.stream === 'stderr')
            .pop()
          this.install_result_message = lastError?.data || 'Installation failed'
          const message = `Could not install firmware: ${this.install_result_message}.`
          notifier.pushError('FILE_FIRMWARE_INSTALL_FAIL', message)
        } else {
          this.install_status = InstallStatus.Succeeded
          this.install_result_message = 'Successfully installed new firmware'
          autopilot_data.reset()
        }
      } catch (error) {
        this.install_status = InstallStatus.Failed
        // Catch Chrome's net:::ERR_UPLOAD_FILE_CHANGED error
        if (error.message && error.message === 'Network Error') {
          this.install_result_message = 'Upload fail. If the file was changed, clean the form and re-select it.'
        } else {
          this.install_result_message = error.response?.data?.detail ?? error.message
        }
        const message = `Could not install firmware: ${this.install_result_message}.`
        notifier.pushError('FILE_FIRMWARE_INSTALL_FAIL', message)
      }
    },
  },
})
</script>

<style scoped>
#update-configs {
  display: grid;
  grid-template-areas: 'modes modes options options options';
  gap: 20px;
}
@media (max-width: 600px) {
  #update-configs {
    grid-template-areas:
      'modes'
      'options';
  }
}
#update-modes {
  grid-area: modes;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
#update-options {
  grid-area: options;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.bl-only-info-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

@media (max-width: 600px) {
  .bl-only-info-action {
    flex-direction: column;
    align-items: flex-end;
  }
}

.install-logs {
  background-color: rgba(0, 0, 0, 0.8);
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-line {
  padding: 2px 4px;
  white-space: pre-wrap;
  word-break: break-word;
}

.info-log {
  color: #ffffff;
}

.error-log {
  color: #ff5252;
  font-weight: bold;
}
</style>
