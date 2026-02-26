<template>
  <v-dialog
    width="350"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title class="text-h5">
        Hotspot Settings
        <v-chip
          v-if="interfaceName"
          small
          class="ml-2"
        >
          {{ interfaceName }}
        </v-chip>
      </v-card-title>

      <v-card-text v-if="loading_credentials">
        <div class="d-flex flex-column align-center py-4">
          <v-progress-circular
            indeterminate
            color="primary"
            class="mb-2"
          />
          <span class="grey--text">Loading settings...</span>
        </div>
      </v-card-text>
      <v-card-text v-else>
        <v-form
          ref="form"
          lazy-validation
        >
          <v-text-field
            v-model="inputed_ssid"
            label="Hotspot SSID"
            hide-details="auto"
            :rules="[isValidSSID]"
          />
          <v-text-field
            v-model="inputed_password"
            label="Hotspot password"
            hide-details="auto"
            :rules="[isValidPassword]"
          />

          <v-checkbox
            v-model="enable_smart_hotspot"
            v-tooltip="'Auto-start hotspot when not connected to a wifi network for some time.'"
            label="Enable smart-hotspot"
          />

          <v-container class="d-flex justify-end">
            <v-btn
              v-if="!saving_settings"
              color="success"
              class="ma-1"
              @click="saveSettings"
            >
              Save
            </v-btn>
          </v-container>
        </v-form>
      </v-card-text>
      <v-card-text v-if="saving_settings">
        Saving settings, please wait...
        <v-progress-linear
          indeterminate
          color="primary"
          class="mb-0"
        />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import { NetworkCredentials } from '@/types/wifi'
import back_axios, { isBackendOffline } from '@/utils/api'

const notifier = new Notifier(wifi_service)

export default Vue.extend({
  name: 'WifiSettingsDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    interfaceName: {
      type: String,
      default: 'wlan0',
    },
  },
  data() {
    return {
      inputed_ssid: '',
      inputed_password: '',
      enable_smart_hotspot: wifi.smart_hotspot_status || false,
      saving_settings: false,
      loading_credentials: false,
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
  },
  watch: {
    show(newVal: boolean): void {
      if (newVal) {
        this.fetchCredentials()
        this.enable_smart_hotspot = wifi.smart_hotspot_status || false
      }
    },
  },
  methods: {
    async saveSettings(): Promise<boolean> {
      if (!this.form.validate()) {
        return false
      }
      this.saving_settings = true
      try {
        const credentials: NetworkCredentials = { ssid: this.inputed_ssid, password: this.inputed_password }

        await back_axios({
          method: 'post',
          url: `${wifi.API_URL_V2}/wifi/hotspot/credentials`,
          data: { interface: this.interfaceName, credentials },
          timeout: 30000,
        })
          .then(() => {
            notifier.pushSuccess(
              'HOTSPOT_CREDENTIALS_UPDATE_SUCCESS',
              `Updated hotspot credentials for ${this.interfaceName}.`,
            )
            wifi.setInterfaceHotspotCredentials({ interface: this.interfaceName, credentials })
            this.$emit('credentials-updated', { interface: this.interfaceName, credentials })
          })
          .catch((error) => {
            notifier.pushBackError('HOTSPOT_CREDENTIALS_UPDATE_FAIL', error, true)
          })

        await back_axios({
          method: 'post',
          url: `${wifi.API_URL}/smart_hotspot`,
          params: { enable: this.enable_smart_hotspot },
          timeout: 10000,
        })
          .then(() => {
            notifier.pushSuccess('SMART_HOTSPOT_TOGGLE_SUCCESS', 'Successfully updated smart-hotspot configuration.')
          })
          .catch((error) => {
            notifier.pushBackError('SMART_HOTSPOT_TOGGLE_FAIL', error, true)
          })
        this.showDialog(false)
        return true
      } catch (error) {
        return false
      } finally {
        this.saving_settings = false
      }
    },
    isValidSSID(input: string): (true | string) {
      return input.length >= 1 ? true : 'SSID cannot be blank.'
    },
    isValidPassword(input: string): (true | string) {
      return input.length >= 8 ? true : 'Password must have at least 8 characters.'
    },
    showDialog(state: boolean): void {
      this.$emit('change', state)
    },
    async fetchCredentials(): Promise<void> {
      this.loading_credentials = true
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL_V2}/wifi/hotspot/${this.interfaceName}`,
        timeout: 10000,
      })
        .then(({ data }) => {
          this.inputed_ssid = data.ssid || ''
          this.inputed_password = data.password || ''
          if (data.ssid && data.password) {
            wifi.setInterfaceHotspotCredentials({
              interface: this.interfaceName,
              credentials: { ssid: data.ssid, password: data.password },
            })
          }
        })
        .catch((error) => {
          if (isBackendOffline(error)) return
          const interfaceCreds = wifi.interface_hotspot_credentials.get(this.interfaceName)
          if (interfaceCreds) {
            this.inputed_ssid = interfaceCreds.ssid || ''
            this.inputed_password = interfaceCreds.password || ''
          } else if (wifi.hotspot_credentials) {
            this.inputed_ssid = wifi.hotspot_credentials.ssid || ''
            this.inputed_password = wifi.hotspot_credentials.password || ''
          }
        })
        .finally(() => {
          this.loading_credentials = false
        })
    },
  },
})
</script>
