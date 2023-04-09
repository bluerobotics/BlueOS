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
            Apply
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
            <v-stepper vertical>
              <v-stepper-step
                v-for="(config, index) in configurations"
                :key="index"
                :step="index + 1"
                :color="getStepColor(config)"
                :complete-icon="getStepIcon(config)"
                :complete="true"
                active
                class="step-label"
              >
                {{ config.title }}
                <small v-if="config.summary">{{ config.summary }}</small>
                <small v-if="config.message" :color="getStepColor(config)">Error: {{ config.message }}</small>
              </v-stepper-step>
            </v-stepper>
            <v-row class="pa-5 pt-10  d-flex flex-column align-center">
              <v-btn
                v-if="apply_failed"
                color="warning"
                :loading="wait_configuration"
                @click="applyConfigurations()"
              >
                Retry
              </v-btn>
              <v-btn
                v-else-if="apply_done"
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

import Vue from 'vue'

import beacon from '@/store/beacon'
import wifi from '@/store/wifi'
import back_axios, { backend_offline_error } from '@/utils/api'

const API_URL = '/bag/v1.0'
const WIZARD_VERSION = 3

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

type ConfigurationStatus = string | undefined

interface Configuration {
  title: string,
  summary: string | undefined,
  promise: Promise<ConfigurationStatus>
  message: undefined | string
  done: boolean
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
      wait_configuration: false,
      // Final configuration
      configurations: [] as Configuration[],
      // Vehicle configuration
      setup_configurations: [] as Configuration[],
    }
  },
  computed: {
    apply_done(): boolean {
      return this.apply_status === ApplyStatus.Done
    },
    apply_failed(): boolean {
      return this.apply_status === ApplyStatus.Failed
    },
  },
  mounted() {
    back_axios({
      method: 'get',
      url: `${API_URL}/get/wizard`,
      timeout: 10000,
    })
      .then((response) => {
        const wizard = response.data
        if (wizard?.version !== WIZARD_VERSION) {
          this.should_open = true
        }
      })
      .catch((error) => {
        if (error === backend_offline_error) {
          return
        }
        this.should_open = true
      })
  },
  methods: {
    nextStep() {
      this.step_number += 1
    },
    getStepIcon(config: Configuration) {
      if (config.done) {
        return 'mdi-check'
      }
      if (config.message === undefined) {
        return 'mdi-loading'
      }
      return 'mdi-alert'
    },
    getStepColor(config: Configuration) {
      if (config.done) {
        return 'success'
      }
      if (config.message === undefined) {
        return 'yellow'
      }
      return 'error'
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
        ...this.setup_configurations,
        {
          title: 'Update wizard version',
          summary: 'Disable wizard for this version'
            + ' it may show again if vehicle configuration updates in future versions',
          promise: this.setWizardVersion(),
          message: undefined,
          done: false,
        },
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
      this.step_number += 1

      this.setup_configurations = [
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
      this.applyConfigurations()
    },
    setupROV() {
      this.vehicle_type = VehicleType.Sub
      this.vehicle_name = 'BlueROV'
      this.step_number += 1
    },
    async setWizardVersion(): Promise<ConfigurationStatus> {
      return back_axios({
        method: 'post',
        url: `${API_URL}/set/wizard`,
        timeout: 5000,
        data: {
          version: WIZARD_VERSION,
        },
      })
        .then(() => undefined)
        .catch((error) => 'Configuration done, but failed to set wizard version: '
          + `${error.message ?? error.response?.data}.`)
    },
    async setHostname(): Promise<ConfigurationStatus> {
      return beacon.setHostname(this.mdns_name)
        .then(() => undefined)
        .catch(() => 'Failed to set vehicle hostname for mDNS')
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
