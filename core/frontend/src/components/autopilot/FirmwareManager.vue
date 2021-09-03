<template>
  <v-card
    elevation="0"
    class="mb-12 pb-12 text-center"
  >
    <v-item-group
      v-model="upload_type"
      mandatory
      class="ma-6"
    >
      <v-item
        v-slot="{ active, toggle }"
        :value="UploadType.Cloud"
      >
        <v-btn
          :color="active ? 'primary' : ''"
          class="mr-2"
          @click="toggle"
        >
          <v-icon class="mr-2">
            mdi-cloud
          </v-icon>
          <div>Choose firmware from repository</div>
        </v-btn>
      </v-item>
      <v-item
        v-slot="{ active, toggle }"
        :value="UploadType.File"
      >
        <v-btn
          :color="active ? 'primary' : ''"
          @click="toggle"
        >
          <v-icon class="mr-2">
            mdi-paperclip
          </v-icon>
          <div>Upload custom firmware file</div>
        </v-btn>
      </v-item>
    </v-item-group>

    <v-form
      v-if="upload_type === UploadType.Cloud"
      ref="form"
      lazy-validation
    >
      <v-select
        v-model="chosen_vehicle"
        :items="vehicle_types"
        label="Vehicle"
        required
        @change="updateAvailableFirmwares"
      />
      <v-select
        v-model="chosen_firmware_url"
        :disabled="disable_firmware_selection"
        :items="showable_firmwares"
        :label="firmware_selector_label"
        :loading="loading_firmware_options"
        required
        @change="setCloudFirmwareChosen"
      />
    </v-form>

    <v-file-input
      v-if="upload_type === UploadType.File"
      show-size
      label="Firmware file"
      @change="setFileFirmware"
    />

    <v-btn
      :disabled="!allow_installing"
      class="mt-6"
      @click="installFirmware"
    >
      <v-icon>mdi-paperclip</v-icon>
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
  </v-card>
</template>

<script lang="ts">
import axios, { AxiosRequestConfig } from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import AutopilotStore from '@/store/autopilot'
import NotificationStore from '@/store/notifications'
import { Firmware, Vehicle } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

const notification_store: NotificationStore = getModule(NotificationStore)
const autopilot_store: AutopilotStore = getModule(AutopilotStore)

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
  File
}

export default Vue.extend({
  name: 'FirmwareManager',
  data() {
    return {
      CloudFirmwareOptionsStatus,
      cloud_firmware_options_status: CloudFirmwareOptionsStatus.NotFetched,
      InstallStatus,
      install_status: InstallStatus.NotStarted,
      UploadType,
      upload_type: UploadType.Cloud,
      chosen_vehicle: null as (Vehicle | null),
      chosen_firmware_url: null as (URL | null),
      available_firmwares: [] as Firmware[],
      firmware_file: null as (Blob | null),
      install_result_message: '',
    }
  },
  computed: {
    firmware_selector_label(): string {
      return this.loading_firmware_options ? 'Fetching available firmwares...' : 'Firmware'
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
    vehicle_types(): {value: string, text: Vehicle}[] {
      return Object.entries(Vehicle).map(
        (vehicle) => ({ value: vehicle[0], text: vehicle[1] }),
      )
    },
    disable_firmware_selection(): boolean {
      return this.chosen_vehicle == null
    },
    showable_firmwares(): {value: URL, text: string}[] {
      return this.available_firmwares.map(
        (firmware) => ({ value: firmware.url, text: firmware.name }),
      )
    },
    allow_installing(): boolean {
      if (this.install_status === InstallStatus.Installing) {
        return false
      }
      if (this.upload_type === UploadType.Cloud) {
        return this.cloud_firmware_options_status === CloudFirmwareOptionsStatus.Chosen
      }
      return this.firmware_file !== null
    },
  },
  methods: {
    async updateAvailableFirmwares(): Promise<void> {
      this.chosen_firmware_url = null
      this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.Fetching
      await axios({
        method: 'get',
        url: `${autopilot_store.API_URL}/available_firmwares`,
        timeout: 10000,
        params: { vehicle: this.chosen_vehicle },
      })
        .then((response) => {
          this.available_firmwares = response.data
          this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.FetchSucceeded
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_service,
            'FIRMWARE_FETCH_FAIL',
            `Could not fetch available firmwares: ${error.message}.`,
          ))
          this.cloud_firmware_options_status = CloudFirmwareOptionsStatus.FetchFailed
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
        timeout: 60000,
      }
      if (this.upload_type === UploadType.Cloud) {
        // Populate request with data for cloud install
        Object.assign(axios_request_config, {
          url: `${autopilot_store.API_URL}/install_firmware_from_url`,
          params: { url: this.chosen_firmware_url },
        })
      } else {
        // Populate request with data for file install
        if (!this.firmware_file) {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Warning,
            autopilot_service,
            'FILE_FIRMWARE_UPLOAD_FAIL',
            'Could not upload firmware: no firmware file selected.',
          ))
          return
        }
        const form_data = new FormData()
        form_data.append('binary', this.firmware_file)
        Object.assign(axios_request_config, {
          url: `${autopilot_store.API_URL}/install_firmware_from_file`,
          headers: { 'Content-Type': 'multipart/form-data' },
          data: form_data,
        })
      }

      await axios(axios_request_config)
        .then(() => {
          this.install_status = InstallStatus.Succeeded
          this.install_result_message = 'Successfully installed new firmware'
        })
        .catch((error) => {
          this.install_status = InstallStatus.Failed
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_service,
            'FILE_FIRMWARE_UPLOAD_FAIL',
            `Could not upload firmware: ${error}.`,
          ))
          try {
            this.install_result_message = error.response.data.message
          } catch {
            this.install_result_message = 'Invalid backend error message.'
          }
        })
    },
  },
})
</script>
