<template>
  <v-dialog
    v-model="should_open"
    transition="dialog-top-transition"
    width="600"
    height="400"
    persistent
  >
    <v-card>
      <v-stepper v-model="step_number">
        <v-stepper-header>
          <v-stepper-step :complete="step_number > 1" step="1">
            Choose Vehicle
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 2" step="2">
            Customize
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 3" step="3">
            Configure
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 3" step="4">
            Done
          </v-stepper-step>
        </v-stepper-header>

        <v-stepper-items>
          <v-stepper-content step="1">
            <div class="d-flex justify-space-between">
              <model-viewer
                v-tooltip="'ROV Setup'"
                :src="sub_model"
                :auto-rotate="false"
                camera-orbit="45deg 75deg 1.5m"
                shadow-intensity="0.3"
                interaction-prompt="none"
                class="model-button ma-2"
                @click="setupROV"
              />

              <model-viewer
                v-tooltip="'Boat Setup'"
                :src="boat_model"
                :auto-rotate="false"
                camera-orbit="-45deg 75deg 2.5m"
                shadow-intensity="0.3"
                interaction-prompt="none"
                class="model-button ma-2"
                @click="setupBoat"
              />
            </div>
          </v-stepper-content>

          <v-stepper-content step="2">
            <div class="d-flex flex-column align-center">
              <v-text-field v-model="vehicle_name" label="Vehicle Name" />
              <v-text-field v-model="mdns_name" label="MDNS Name" />
            </div>

            <v-alert :value="configuration_failed" type="error">
              {{ error_message }}
            </v-alert>

            <v-row class="pa-5">
              <v-btn
                color="warning"
                :loading="wait_configuration"
                @click="step_number = 1"
              >
                Return
              </v-btn>
              <v-spacer />
              <v-btn
                color="primary"
                :loading="wait_configuration"
                @click="setupConfiguration"
              >
                Continue
              </v-btn>
            </v-row>
          </v-stepper-content>

          <v-stepper-content step="3">
            <div class="d-flex flex-column align-center">
              <component
                :is="current_page"
                v-bind="current_page_bind"
                @next="handleNextVehicleConfiguration"
              />
            </div>
            <v-row class="pa-5 pt-10 flex-row justify-space-around align-center grow">
              <v-btn
                v-if="apply_failed"
                color="warning"
                :loading="wait_configuration"
                @click="applyConfigurations()"
              >
                Retry
              </v-btn>
              <v-btn
                color="error"
                @click="cancel()"
              >
                Cancel
              </v-btn>
              <v-btn
                v-if="apply_done"
                color="primary"
                @click="nextStep()"
              >
                Continue
              </v-btn>
            </v-row>
          </v-stepper-content>

          <v-stepper-content step="4">
            <v-alert :value="true" type="success">
              Your vehicle is ready to use!
            </v-alert>
            <v-row class="pa-5">
              <v-spacer />
              <v-btn color="primary" @click="close">
                Close
              </v-btn>
            </v-row>
          </v-stepper-content>
          <v-stepper-content step="100">
            <v-alert :value="true" type="error">
              Configuration was aborted.
            </v-alert>
            <v-row class="pa-5">
              <v-spacer />
              <v-btn color="primary" @click="close">
                Close
              </v-btn>
            </v-row>
          </v-stepper-content>
        </v-stepper-items>
      </v-stepper>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import '@google/model-viewer/dist/model-viewer'

import Vue from 'vue'

import { availableFirmwares, installFirmwareFromUrl } from '@/components/autopilot/AutopilotManagerUpdater'
import bag from '@/store/bag'
import beacon from '@/store/beacon'
import wifi from '@/store/wifi'
import { Firmware, Vehicle } from '@/types/autopilot'
import back_axios from '@/utils/api'

import ActionStepper, { Configuration, ConfigurationStatus } from './ActionStepper.vue'
import RequireInternet from './RequireInternet.vue'

const WIZARD_VERSION = 4

const models = require.context(
  '/src/assets/vehicles/models/',
  true,
  /\.(glb|json)$/,
)

enum VehicleType {
  Sub,
  Boat,
}

enum ApplyStatus {
  Waiting,
  Done,
  Failed,
}

// There is no type that could serve for generic binds and generic vue components
interface VehicleConfigurationPage {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  binds: any,
}

export default Vue.extend({
  name: 'Wizard',
  data() {
    return {
      boat_model: models('./boat/UNDEFINED.glb'),
      configuration_failed: false,
      error_message: 'The operation failed!',
      apply_status: ApplyStatus.Waiting,
      mdns_name: 'blueos',
      should_open: false,
      step_number: 1,
      sub_model: models('./bluerov.glb'),
      vehicle_name: 'blueos',
      vehicle_type: VehicleType.Sub,
      vehicle_image: null as string | null,
      wait_configuration: false,
      // Final configuration
      configurations: [] as Configuration[],
      // Vehicle configuration
      setup_configurations: [] as Configuration[],
      // Vehicle configuration page logic
      vehicle_configuration_pages: [] as VehicleConfigurationPage[],
      configuration_page_index: 0,
    }
  },
  computed: {
    apply_done(): boolean {
      return this.apply_status === ApplyStatus.Done
    },
    apply_failed(): boolean {
      return this.apply_status === ApplyStatus.Failed
    },
    configuration_pages(): VehicleConfigurationPage[] {
      return [
        ...this.vehicle_configuration_pages,
        {
          page: ActionStepper,
          binds: {
            configurations: this.configurations,
          },
        },
      ]
    },
    current_page(): unknown {
      return this.configuration_pages[this.configuration_page_index].page
    },
    current_page_bind(): unknown {
      return this.configuration_pages[this.configuration_page_index].binds
    },
  },

  watch: {
    apply_done(new_value: boolean) {
      if (new_value) {
        this.setWizardVersion()
      }
    },
  },
  async mounted() {
    const wizard = await bag.getData('wizard')

    // Failed to communicate with the bag service
    if (wizard === undefined) {
      return
    }

    if (wizard?.version !== WIZARD_VERSION) {
      this.should_open = true
    }
  },
  methods: {
    close() {
      this.should_open = false
      setTimeout(() => { window.location.reload() }, 500)
    },
    cancel() {
      this.step_number = 100
    },
    nextStep() {
      this.step_number += 1
    },
    handleNextVehicleConfiguration() {
      this.configuration_page_index += 1
      if (this.configuration_page_index >= this.vehicle_configuration_pages.length) {
        this.applyConfigurations()
      }
    },
    async applyConfigurations() {
      this.configurations = [
        {
          title: 'Set custom vehicle name',
          summary: `Set vehicle name for the user: ${this.vehicle_name}`,
          promise: this.setHostname(),
          message: undefined,
          done: false,
        },
        {
          title: 'Set vehicle hostname',
          summary: `Set hostname to be used for mDNS address: ${this.mdns_name}.local`,
          promise: this.setVehicleName(),
          message: undefined,
          done: false,
        },
        {
          title: 'Set vehicle image',
          summary: 'Set image to be used for vehicle thumbnail',
          promise: this.setVehicleImage(),
          message: undefined,
          done: false,
        },
        ...this.setup_configurations,
      ]

      this.apply_status = ApplyStatus.Waiting
      this.apply_status = await Promise.all(this.configurations.map(async (config) => {
        if (!config.done) {
          config.message = await config.promise
          config.done = config.message === undefined
        }
        return config
      })).then((configs) => configs.every((config) => config.done)) ? ApplyStatus.Done : ApplyStatus.Failed
    },
    setupBoat() {
      this.vehicle_type = VehicleType.Boat
      this.vehicle_name = 'BlueBoat'
      this.vehicle_image = '/vehicles/images/bb120.png'
      this.step_number += 1

      this.vehicle_configuration_pages = [
        {
          page: RequireInternet,
          binds: {},
        },
      ]

      this.setup_configurations = [
        {
          title: 'Install stable boat firmware',
          summary: 'Download and install a desirable stable firmware on the vehicle',
          promise: this.installLatestStableFirmware(Vehicle.Rover),
          message: undefined,
          done: false,
        },
        {
          title: 'Disable Wi-Fi hotspot',
          summary: 'Wi-Fi hotspot need to be disable to not interfere with onboard radio',
          promise: this.disableWifiHotspot(),
          message: undefined,
          done: false,
        },
        {
          title: 'Disable smart Wi-Fi hotspot',
          summary: 'Disable hotspot to be turned on if there is no Wi-Fi network available',
          promise: this.disableSmartWifiHotspot(),
          message: undefined,
          done: false,
        },
      ]
    },
    async setupConfiguration() {
      this.step_number += 1
    },
    setupROV() {
      this.vehicle_type = VehicleType.Sub
      this.vehicle_name = 'BlueROV'
      this.vehicle_image = '/vehicles/images/bluerov2.png'
      this.step_number += 1

      this.vehicle_configuration_pages = [
        {
          page: RequireInternet,
          binds: {},
        },
      ]

      this.setup_configurations = [
        {
          title: 'Install stable sub firmware',
          summary: 'Download and install a desirable stable firmware on the vehicle',
          promise: this.installLatestStableFirmware(Vehicle.Sub),
          message: undefined,
          done: false,
        },
      ]
    },
    async setWizardVersion(): Promise<ConfigurationStatus> {
      const failed = 'Configuration done, but failed to set wizard version.'
      const payload = { version: WIZARD_VERSION }
      return bag.setData('wizard', payload)
        // eslint-disable-next-line no-confusing-arrow
        .then((result) => result ? undefined : failed)
        .catch(() => failed)
    },
    async setHostname(): Promise<ConfigurationStatus> {
      return beacon.setHostname(this.mdns_name)
        .then(() => undefined)
        .catch(() => 'Failed to set vehicle hostname for mDNS')
    },
    async setVehicleImage(): Promise<ConfigurationStatus> {
      const failed = 'Failed to set vehicle Image.'
      const payload = { url: this.vehicle_image }
      return bag.setData('vehicle.image_path', payload)
        // eslint-disable-next-line no-confusing-arrow
        .then((result) => result ? undefined : failed)
        .catch(() => failed)
    },
    async setVehicleName(): Promise<ConfigurationStatus> {
      return beacon.setVehicleName(this.vehicle_name)
        .then(() => undefined)
        .catch(() => 'Failed to set custom vehicle name')
    },
    async disableWifiHotspot(): Promise<ConfigurationStatus> {
      return back_axios({
        method: 'post',
        url: `${wifi.API_URL}/hotspot`,
        params: { enable: false },
        timeout: 20000,
      })
        .then(() => undefined)
        .catch((error) => `Failed to disable wifi hotspot: ${error.message ?? error.response?.data}.`)
    },
    async disableSmartWifiHotspot(): Promise<ConfigurationStatus> {
      return back_axios({
        method: 'post',
        url: `${wifi.API_URL}/smart_hotspot`,
        params: { enable: false },
        timeout: 10000,
      })
        .then(() => undefined)
        .catch((error) => `Failed to disable smart wifi hotspot: ${error.message ?? error.response?.data}.`)
    },
    async installLatestStableFirmware(vehicle: Vehicle): Promise<ConfigurationStatus> {
      return availableFirmwares(vehicle)
        .then((firmwares: Firmware[]) => {
          const found: Firmware | undefined = firmwares.find((firmware) => firmware.name.includes('STABLE'))
          if (found === undefined) {
            return `Failed to find a stable version for vehicle (${vehicle})`
          }
          return installFirmwareFromUrl(found.url, true)
            .then(() => undefined)
            .catch((error) => `Failed to install firmware: ${error.message ?? error.response?.data}.`)
        })
        .catch((error) => `Failed to install stable firmware: ${error.message ?? error.response?.data}.`)
    },
  },
})
</script>

<style scoped>
.model-button {
  display: inline-block;
  padding: 10px 20px;
  border: 2px solid #888;
  cursor: pointer;
  text-align: center;
  user-select: none;
  transition: background-color 0.3s, color 0.3s;
}

.model-button:hover {
  background-color: #00000040;
  color: #fff;
}

.step-label {
  text-shadow: 0px 0px 0px !important;
}
</style>
