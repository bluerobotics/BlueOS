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
            Configuration
          </v-stepper-step>

          <v-divider />

          <v-stepper-step step="3" :complete="is_ok">
            Done
          </v-stepper-step>
        </v-stepper-header>

        <v-stepper-items>
          <v-stepper-content step="1">
            <div class="d-flex justify-space-between">
              <model-viewer
                :src="sub_model"
                :auto-rotate="false"
                camera-orbit="45deg 75deg 1.5m"
                shadow-intensity="0.3"
                interaction-prompt="none"
                class="model-button ma-2"
                @click="setupROV"
              />

              <model-viewer
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
const WIZARD_VERSION = 2

const models = require.context(
  '/src/assets/vehicles/models/',
  true,
  /\.(glb|json)$/,
)

enum VehicleType {
  Sub,
  Boat,
}

export default Vue.extend({
  name: 'Wizard',
  data() {
    return {
      boat_model: models('./boat/UNDEFINED.glb'),
      configuration_failed: false,
      error_message: 'The operation failed!',
      is_ok: false,
      mdns_name: 'blueos',
      should_open: false,
      step_number: 1,
      sub_model: models('./bluerov.glb'),
      vehicle_name: 'blueos',
      vehicle_type: VehicleType.Sub,
      wait_configuration: false,
    }
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
    setupBoat() {
      this.vehicle_type = VehicleType.Boat
      this.vehicle_name = 'BlueBoat'
      this.step_number += 1
    },
    async setupConfiguration() {
      this.wait_configuration = true

      if (this.vehicle_type === VehicleType.Boat) {
        if (!await this.disableWifiHotspot()) {
          return
        }
      }

      if (await beacon.setHostname(this.mdns_name) && await beacon.setVehicleName(this.vehicle_name)) {
        await this.setWizardVersion()
        return
      }
      this.configuration_failed = true
      this.wait_configuration = false
    },
    setupROV() {
      this.vehicle_type = VehicleType.Sub
      this.vehicle_name = 'BlueROV'
      this.step_number += 1
    },
    async setWizardVersion(): Promise<void> {
      return back_axios({
        method: 'post',
        url: `${API_URL}/set/wizard`,
        timeout: 5000,
        data: {
          version: WIZARD_VERSION,
        },
      })
        .then(() => {
          this.wait_configuration = false
          this.step_number = 3
          this.is_ok = true
        })
        .catch((error) => {
          this.configuration_failed = true
          this.wait_configuration = false
          this.error_message = 'Configuration done, but failed to set wizard version: '
            + `${error.message ?? error.response?.data}.`
        })
    },
    async disableWifiHotspot(): Promise<boolean> {
      return back_axios({
        method: 'post',
        url: `${wifi.API_URL}/hotspot`,
        params: { enable: false },
        timeout: 20000,
      })
        .then(() => true)
        .catch((error) => {
          this.configuration_failed = true
          this.wait_configuration = false
          this.error_message = `Failed to disable wifi hotspot: ${error.message ?? error.response?.data}.`
          return false
        })
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
</style>
