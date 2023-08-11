<template>
  <v-dialog
    v-model="should_open"
    transition="dialog-top-transition"
    width="800"
    height="400"
    persistent
  >
    <v-card>
      <v-stepper v-model="step_number">
        <v-stepper-header>
          <v-stepper-step :complete="step_number > 1" step="1">
            Check internet
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 2" step="2">
            Choose Vehicle
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 3" step="3">
            Customize
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 4" step="4">
            Configure
          </v-stepper-step>

          <v-divider />

          <v-stepper-step :complete="step_number > 5" step="5">
            Apply
          </v-stepper-step>
        </v-stepper-header>

        <v-stepper-items>
          <v-stepper-content step="0">
            <v-card class="ma-2 pa-5">
              <div class="welcome" style="display: flex; justify-content: center; align-items: center; width: 100%;">
                Welcome to BlueOS!
              </div>
              Welcome to BlueOS!
              In this setup wizard we will guide you through the initial configuration of your vehicle.
              including setting up the vehicle name, hostname, and <b>firmware</b>.
              If your vehicle is already set up, you can skip this wizard.
            </v-card>
            <v-row class="pa-5 justify-space-between">
              <v-btn
                color="warning darken"
                @click="setWizardVersion(); cancel()"
              >
                Skip Wizard
              </v-btn>
              <v-btn
                color="primary"
                @click="nextStep()"
              >
                Start
              </v-btn>
            </v-row>
          </v-stepper-content>
          <v-stepper-content step="1">
            <RequireInternet v-if="step_number === 1" @next="nextStep()" />
            <v-row class="pa-5">
              <v-btn

                color="warning"
                @click="cancel()"
              >
                Cancel wizard
              </v-btn>
            </v-row>
          </v-stepper-content>
          <v-stepper-content step="2">
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
              <v-icon
                v-tooltip="'Other Vehicle Setup'"
                class="model-button ma-2 other-button"
                @click="setupOther"
              >
                mdi-ufo-outline
              </v-icon>
            </div>
            <v-row class="pa-5">
              <v-btn
                color="warning"
                @click="cancel"
              >
                Ask me later
              </v-btn>
              <v-spacer />
              <v-btn
                color="error"
                @click="setWizardVersion(); cancel()"
              >
                Don't show again
              </v-btn>
            </v-row>
          </v-stepper-content>

          <v-stepper-content step="3">
            <div class="d-flex flex-column align-center">
              <v-text-field v-model="vehicle_name" label="Vehicle Name" />
              <v-text-field v-model="mdns_name" label="MDNS Name" />
            </div>
            <DefaultParamLoader
              v-model="params"
              :vehicle="vehicle_type"
            />
            <v-alert :value="configuration_failed" type="error">
              {{ error_message }}
            </v-alert>

            <v-row class="pa-5">
              <v-btn
                color="warning"
                @click="step_number = 1"
              >
                Return
              </v-btn>
              <v-spacer />
              <v-btn
                color="primary"
                @click="setupConfiguration"
              >
                Continue
              </v-btn>
            </v-row>
          </v-stepper-content>

          <v-stepper-content step="4">
            <div class="d-flex flex-column align-center">
              <component
                :is="current_page"
                v-bind="current_page_bind"
                @next="handleNextVehicleConfiguration"
              />
            </div>
            <v-row class="pa-5 pt-10 flex-row justify-space-around align-center grow">
              <v-btn
                :color="retry_count == 0 ? 'success' : 'error'"
                :loading="apply_in_progress"
                :disabled="apply_in_progress"
                @click="applyConfigurations()"
              >
                {{ retry_count == 0 ? "Apply" : "Retry" }}
              </v-btn>
              <v-btn
                v-if="allow_abort"
                :loading="apply_in_progress"
                :disabled="apply_in_progress"
                color="warning"
                @click="abort()"
              >
                Abort
              </v-btn>
            </v-row>
          </v-stepper-content>

          <v-stepper-content step="5">
            <v-alert :value="true" type="success">
              Your vehicle is ready to use!
            </v-alert>
          </v-stepper-content>
          <v-stepper-content step="100">
            <v-alert :value="true" type="warning">
              Configuration was skipped.
            </v-alert>
            <v-row class="pa-5">
              <v-spacer />
              <v-btn color="primary" @click="should_open = false">
                Close
              </v-btn>
            </v-row>
          </v-stepper-content>
          <v-stepper-content step="101">
            <v-alert :value="true" type="warning">
              Configuration was aborted, some settings have failed to apply.
            </v-alert>
            <v-row class="pa-5">
              <v-spacer />
              <v-btn color="primary" @click="should_open = false">
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

import { SemVer } from 'semver'
import Vue from 'vue'

import {
  availableFirmwares,
  fetchFirmwareInfo,
  installFirmwareFromUrl,
} from '@/components/autopilot/AutopilotManagerUpdater'
import mavlink2rest from '@/libs/MAVLink2Rest'
import { MavCmd } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import ardupilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import bag from '@/store/bag'
import beacon from '@/store/beacon'
import wifi from '@/store/wifi'
import { Firmware, Vehicle, vehicleTypeFromString } from '@/types/autopilot'
import { Dictionary } from '@/types/common'
import back_axios from '@/utils/api'
import { sleep } from '@/utils/helper_functions'

import ActionStepper, { Configuration, ConfigurationStatus } from './ActionStepper.vue'
import DefaultParamLoader from './DefaultParamLoader.vue'
import RequireInternet from './RequireInternet.vue'

const WIZARD_VERSION = 4

const models = require.context(
  '/src/assets/vehicles/models/',
  true,
  /\.(glb|json)$/,
)

enum ApplyStatus {
  Waiting,
  Done,
  InProgress,
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
  components: {
    DefaultParamLoader,
    RequireInternet,
  },
  data() {
    return {
      boat_model: models('./boat/UNDEFINED.glb'),
      configuration_failed: false,
      error_message: 'The operation failed!',
      apply_status: ApplyStatus.Waiting,
      mdns_name: 'blueos',
      should_open: false,
      step_number: 0,
      sub_model: models('./bluerov.glb'),
      vehicle_name: 'blueos',
      vehicle_type: Vehicle.Sub,
      vehicle_image: null as string | null,
      // Allow us to check if the user is stuck in retry
      retry_count: 0,
      params: {} as Dictionary<number>,
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
    allow_abort(): boolean {
      return this.retry_count > 2
    },
    apply_done(): boolean {
      return this.apply_status === ApplyStatus.Done
    },
    apply_in_progress(): boolean {
      return this.apply_status === ApplyStatus.InProgress
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
        setTimeout(() => { this.nextStep() }, 2000)
      }
    },
    step_number: {
      handler(new_value: number) {
        if (new_value === 5) {
          this.delayed_close()
        }
      },
    },
  },
  async mounted() {
    this.retry_count = 0

    fetchFirmwareInfo()
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
    delayed_close() {
      setTimeout(() => { this.close() }, 3000)
    },
    close() {
      this.should_open = false
      setTimeout(() => { window.location.reload() }, 500)
    },
    cancel() {
      this.step_number = 100
    },
    abort() {
      this.step_number = 101
    },
    nextStep() {
      this.step_number += 1
    },
    handleNextVehicleConfiguration() {
      this.configuration_page_index += 1
    },
    async finalConfigurations() {
      if (this.configurations.isEmpty()) {
        this.configurations = [
          {
            title: 'Set custom vehicle name',
            summary: `Set vehicle name for the user: ${this.vehicle_name}`,
            promise: () => this.setHostname(),
            message: undefined,
            done: false,
            skip: false,
          },
          {
            title: 'Set vehicle hostname',
            summary: `Set hostname to be used for mDNS address: ${this.mdns_name}.local`,
            promise: () => this.setVehicleName(),
            message: undefined,
            done: false,
            skip: false,
          },
          {
            title: 'Set vehicle image',
            summary: 'Set image to be used for vehicle thumbnail',
            promise: () => this.setVehicleImage(),
            message: undefined,
            done: false,
            skip: false,
          },
          ...this.setup_configurations,
        ]
      }
    },
    async applyConfigurations() {
      this.apply_status = ApplyStatus.InProgress
      this.apply_status = await Promise.all(this.configurations.map(async (config) => {
        config.message = undefined
        if (!config.done && !config.skip) {
          config.message = await config.promise()
          config.done = config.message === undefined
        }
        return config
      })).then((configs) => configs.every((config) => config.done || config.skip))
        ? ApplyStatus.Done : ApplyStatus.Failed
      this.retry_count += 1
    },
    setupBoat() {
      this.vehicle_type = Vehicle.Rover
      this.vehicle_name = 'BlueBoat'
      this.vehicle_image = '/vehicles/images/bb120.png'
      this.step_number += 1

      this.vehicle_configuration_pages = [
      ]

      this.setup_configurations = [
        {
          title: 'Update boat firmware',
          summary: 'Download and install a desirable stable firmware on the vehicle',
          promise: () => this.installLatestStableFirmware(Vehicle.Rover),
          message: undefined,
          done: false,
          skip: false,
        },
        {
          title: 'Disable Wi-Fi hotspot',
          summary: 'Wi-Fi hotspot need to be disable to not interfere with onboard radio',
          promise: () => this.disableWifiHotspot(),
          message: undefined,
          done: false,
          skip: false,
        },
        {
          title: 'Disable smart Wi-Fi hotspot',
          summary: 'Disable hotspot to be turned on if there is no Wi-Fi network available',
          promise: () => this.disableSmartWifiHotspot(),
          message: undefined,
          done: false,
          skip: false,
        },
      ]
    },
    setupOther() {
      this.step_number += 1
      this.vehicle_configuration_pages = [
      ]
      this.vehicle_type = Vehicle.Other
    },
    async setupConfiguration() {
      this.step_number += 1
      if (this.step_number >= 3 && this.configuration_page_index >= this.vehicle_configuration_pages.length) {
        this.finalConfigurations()
      }
    },
    setupROV() {
      this.vehicle_type = Vehicle.Sub
      this.vehicle_name = 'BlueROV'
      this.vehicle_image = '/vehicles/images/bluerov2.png'
      this.step_number += 1

      this.vehicle_configuration_pages = [
      ]

      this.setup_configurations = [
        {
          title: 'Install stable sub firmware',
          summary: 'Download and install a desirable stable firmware on the vehicle',
          promise: () => this.installLatestStableFirmware(Vehicle.Sub),
          message: undefined,
          done: false,
          skip: false,
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
      if (this.retry_count) {
        console.debug('Going to reboot flight controller on retry.')
        mavlink2rest.sendMessage(
          {
            header: {
              system_id: 255,
              component_id: 0,
              sequence: 0,
            },
            message: {
              type: 'COMMAND_LONG',
              // 0: Nothing,
              // 1: Reboot autopilot,
              // 2: Shutdown autopilot,
              // 3: Reboot autopilot and keep it in the bootloader until upgraded.
              param1: 1,
              param2: 0, // Companion
              param3: 0, // Component
              param4: 0, // Component ID for param3
              param5: 0,
              param6: 0,
              param7: 0,
              command: {
                type: MavCmd.MAV_CMD_PREFLIGHT_REBOOT_SHUTDOWN,
              },
              target_system: ardupilot_data.system_id,
              target_component: 1,
              confirmation: 0,
            },
          },
        )
        // Wait for 20 seconds for flight controller to reboot
        await sleep(20000)
      }

      return availableFirmwares(vehicle)
        .then((firmwares: Firmware[]) => {
          const found: Firmware | undefined = firmwares.find((firmware) => firmware.name.includes('STABLE'))
          if (found === undefined) {
            return `Failed to find a stable version for vehicle (${vehicle})`
          }
          const newVersion = new SemVer(found?.name.replace('STABLE-', '').trim())
          const currentVersion = autopilot?.firmware_info?.version ?? new SemVer('0.0.0')
          const vehicleType = vehicleTypeFromString(autopilot?.vehicle_type ?? '')
          if (vehicleType === vehicle && newVersion <= currentVersion) {
            // TODO: allow returning strings on success
            return undefined // 'Firmware is already up to date.'
          }
          return installFirmwareFromUrl(found.url, true, this.params)
            .then(() => undefined)
            .catch((error) => `Failed to install firmware: ${error.message ?? error.response?.data}.`)
        })
        .catch((error) => `Failed to fetch available firmware: ${error.message ?? error.response?.data}.`)
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
.other-button {
  width: 300px;
  height: 150px;
  font-size: 100px;
}

.welcome {
  font-size: 30px;
  font-weight: bold;
  margin-bottom: 20px;
}
</style>
