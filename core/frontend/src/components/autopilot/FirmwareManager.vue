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
          v-if="only_bootloader_boards_available"
          v-model="chosen_board"
          :items="available_boards"
          label="Board"
          class="ma-1 pa-0"
          @change="chosen_vehicle = null"
        />
        <div
          v-if="upload_type === UploadType.Cloud"
        >
          <v-select
            v-model="chosen_vehicle"
            :items="vehicle_types"
            label="Vehicle type"
            :hint="vehicle_changed ? vehicle_change_warning : ''"
            :persistent-hint="vehicle_changed"
            required
            class="ma-1 pa-0"
            @change="updateAvailableFirmwares"
          >
            <template
              v-if="vehicle_changed"
              #append-outer
            >
              <v-icon color="warning">
                mdi-alert
              </v-icon>
            </template>
          </v-select>
          <div class="d-flex">
            <v-select
              v-model="chosen_firmware_url"
              class="ma-1 pa-0"
              :disabled="disable_firmware_selection"
              :items="showable_firmwares"
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
    <v-alert
      v-if="is_untested_firmware"
      type="warning"
      class="mt-6 mb-0"
      dense
      text
    >
      {{ untested_firmware_message }}
      <v-btn
        v-if="settings.skip_untested_firmware_warning"
        small
        text
        @click="enableUntestedWarning"
      >
        Warn me again
      </v-btn>
    </v-alert>
    <v-btn
      :disabled="!allow_installing"
      class="mt-6"
      color="primary"
      @click="requestInstall"
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
      width="300"
    >
      <v-card
        color="primary"
        dark
      >
        <v-card-text>
          Installing firmware. Please wait.
          <v-progress-linear
            indeterminate
            color="white"
            class="mb-0"
          />
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

    <WarningDialog
      v-model="show_untested_warning"
      :message="untested_firmware_message"
      confirm-label="Install anyway"
      @confirm="confirmUntestedInstall"
    >
      <v-checkbox
        v-model="skip_untested_warning_next_time"
        dense
        hide-details
        label="Do not warn me again"
      />
    </WarningDialog>
  </v-card>
</template>

<script lang="ts">
import { AxiosRequestConfig } from 'axios'
import { coerce } from 'semver'
import Vue from 'vue'

import WarningDialog from '@/components/common/WarningDialog.vue'
import Notifier from '@/libs/notifier'
import { fetchParamSets, ParamSets, paramSetsForFirmware } from '@/libs/parameter_repository'
import settings from '@/libs/settings'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import commander from '@/store/commander'
import {
  Firmware,
  FirmwareVehicleType,
  firmwareVehicleTypeFromVehicle,
  FlightController,
  FlightControllerFlags,
  Vehicle,
} from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios, { isBackendOffline } from '@/utils/api'

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
  components: {
    WarningDialog,
  },
  data() {
    const { current_board } = autopilot
    const { rebootOnBoardComputer, requestOnBoardComputerReboot } = commander
    return {
      autopilot,
      settings,
      cloud_firmware_options_status: CloudFirmwareOptionsStatus.NotFetched,
      install_status: InstallStatus.NotStarted,
      UploadType,
      upload_type: UploadType.Cloud,
      chosen_board: current_board as (FlightController | null),
      chosen_vehicle: null as (Vehicle | null),
      chosen_firmware_url: null as (URL | null),
      available_firmwares: [] as Firmware[],
      all_param_sets: {} as ParamSets,
      show_untested_warning: false,
      skip_untested_warning_next_time: false,
      firmware_file: null as (Blob | null),
      install_result_message: '',
      rebootOnBoardComputer,
      requestOnBoardComputerReboot,
    }
  },
  computed: {
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
    current_vehicle(): Vehicle | null {
      const firmware = autopilot.firmware_vehicle_type
      if (firmware === null) {
        return null
      }
      const match = Object.values(Vehicle).find(
        (vehicle) => firmwareVehicleTypeFromVehicle(vehicle) === firmware,
      )
      return match ?? null
    },
    vehicle_changed(): boolean {
      return this.chosen_vehicle !== null
        && this.current_vehicle !== null
        && this.chosen_vehicle !== this.current_vehicle
    },
    vehicle_change_warning(): string {
      return `Installing this firmware will change the vehicle from ${this.current_vehicle} to ${this.chosen_vehicle}.`
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
    target_board(): FlightController | null {
      if (this.only_bootloader_boards_available) {
        return this.chosen_board
      }
      return autopilot.current_board
    },
    available_boards(): {value: FlightController, text: string}[] {
      return this.no_sitl_boards.map(
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
      return this.available_firmwares
        .map((firmware) => ({ value: firmware.url, text: firmware.name }))
        .filter((firmware) => firmware.text !== 'OFFICIAL')
        .sort((a, b) => {
          const release_show_order = ['dev', 'beta', 'stable']
          const prior_a = release_show_order.indexOf(a.text.toLowerCase().split('-')[0])
          const prior_b = release_show_order.indexOf(b.text.toLowerCase().split('-')[0])
          return prior_a > prior_b ? 1 : -1
        })
        .reverse()
    },
    // Blue Robotics only curates parameters for firmwares it has tested, so a version resolving to no parameter
    // set has not been vetted. An empty repository means it could not be fetched, which proves nothing.
    is_untested_firmware(): boolean {
      const board = this.target_board
      if (this.upload_type !== UploadType.Cloud || this.chosen_vehicle === null || board === null) {
        return false
      }
      if (Object.keys(this.all_param_sets).length === 0) {
        return false
      }
      const chosen = this.available_firmwares.find((firmware) => firmware.url === this.chosen_firmware_url)
      if (chosen === undefined) {
        return false
      }
      // Cloud firmware names look like "STABLE-4.5.7"; BETA and DEV carry no version and are untested by nature
      const param_sets = paramSetsForFirmware(
        this.all_param_sets,
        firmwareVehicleTypeFromVehicle(this.chosen_vehicle),
        coerce(chosen.name),
        board,
      )
      return Object.keys(param_sets).length === 0
    },
    untested_firmware_message(): string {
      return 'Blue Robotics has not tested this firmware with your vehicle and flight controller.'
        + ' It may not behave as expected.'
    },
    allow_installing(): boolean {
      if (!autopilot_data.is_safe) {
        return false
      }
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
    'autopilot.firmware_vehicle_type': {
      handler(new_value: FirmwareVehicleType | null): void {
        if (this.chosen_vehicle === null && new_value !== null) {
          this.setVehicleFromFirmware()
        }
      },
      immediate: true,
    },
  },
  async mounted(): Promise<void> {
    if (this.only_bootloader_boards_available) {
      this.setFirstNoSitlBoard()
    }
    this.all_param_sets = await fetchParamSets().catch(() => ({}))
  },
  methods: {
    requestInstall(): void {
      if (this.is_untested_firmware && !settings.skip_untested_firmware_warning) {
        this.show_untested_warning = true
        return
      }
      this.installFirmware()
    },
    confirmUntestedInstall(): void {
      if (this.skip_untested_warning_next_time) {
        settings.skip_untested_firmware_warning = true
      }
      this.installFirmware()
    },
    enableUntestedWarning(): void {
      settings.skip_untested_firmware_warning = false
      this.skip_untested_warning_next_time = false
    },
    setFirstNoSitlBoard(): void {
      const [first_board] = this.no_sitl_boards
      this.chosen_board = first_board
    },
    setVehicleFromFirmware(): void {
      if (this.current_vehicle !== null) {
        this.chosen_vehicle = this.current_vehicle
        this.updateAvailableFirmwares()
      }
    },
    async updateAvailableFirmwares(): Promise<void> {
      this.chosen_firmware_url = null
      this.available_firmwares = []
      this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.Fetching
      await back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/available_firmwares`,
        timeout: 30000,
        params: { vehicle: this.chosen_vehicle, board_name: this.target_board?.name },
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
      const axios_request_config: AxiosRequestConfig = {
        method: 'post',
      }
      if (this.upload_type === UploadType.Cloud) {
        // Populate request with data for cloud install
        Object.assign(axios_request_config, {
          url: `${autopilot.API_URL}/install_firmware_from_url`,
          params: { url: this.chosen_firmware_url, board_name: this.target_board?.name },
        })
      } else if (this.upload_type === UploadType.Restore) {
        // Populate request with data for restore install
        Object.assign(axios_request_config, {
          url: `${autopilot.API_URL}/restore_default_firmware`,
          params: { board_name: this.target_board?.name },
        })
      } else {
        // Populate request with data for file install
        if (!this.firmware_file) {
          const message = 'Could not upload firmware: no firmware file selected.'
          notifier.pushWarning('FILE_FIRMWARE_UPLOAD_FAIL', message)
          return
        }
        const form_data = new FormData()
        form_data.append('binary', this.firmware_file)
        Object.assign(axios_request_config, {
          url: `${autopilot.API_URL}/install_firmware_from_file`,
          headers: { 'Content-Type': 'multipart/form-data' },
          params: { board_name: this.target_board?.name },
          data: form_data,
        })
      }

      await back_axios(axios_request_config)
        .then(() => {
          this.install_status = InstallStatus.Succeeded
          this.install_result_message = 'Successfully installed new firmware'
          autopilot_data.reset()
        })
        .catch((error) => {
          this.install_status = InstallStatus.Failed
          if (isBackendOffline(error)) { return }
          // Catch Chrome's net:::ERR_UPLOAD_FILE_CHANGED error
          if (error.message && error.message === 'Network Error') {
            this.install_result_message = 'Upload fail. If the file was changed, clean the form and re-select it.'
          } else {
            this.install_result_message = error.response?.data?.detail ?? error.message
          }
          const message = `Could not install firmware: ${this.install_result_message}.`
          notifier.pushError('FILE_FIRMWARE_INSTALL_FAIL', message)
        })
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
</style>
