<template>
  <v-dialog
    width="300"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title class="text-h5">
        {{ t`Wifi settings` }}
      </v-card-title>

      <v-card-text>
        <v-form
          ref="form"
          lazy-validation
        >
          <v-text-field
            v-model="inputed_ssid"
            :label="t`Hotspot SSID`"
            hide-details="auto"
            :rules="[isValidSSID]"
          />
          <v-text-field
            v-model="inputed_password"
            :label="t`Hotspot password`"
            hide-details="auto"
            :rules="[isValidPassword]"
          />
          <v-select
            v-if="interfaces.length > 1"
            id="hotspot-interface-select"
            v-model="selected_hotspot_interface"
            :items="interfaces"
            :label="t`Hotspot interface`"
            hide-details="auto"
          />

          <v-checkbox
            v-model="enable_smart_hotspot"
            v-tooltip="t`Auto-start hotspot when not connected to a wifi network for some time.`"
            :label="t`Enable smart-hotspot`"
          />

          <v-container class="d-flex justify-end">
            <v-btn
              v-if="!saving_settings"
              color="success"
              class="ma-1"
              @click="saveSettings"
            >
              {{ t`Save` }}
            </v-btn>
          </v-container>
        </v-form>
      </v-card-text>
      <v-card-text v-if="saving_settings">
        {{ t`Saving settings, please wait...` }}
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
import { t } from 'ttag'
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import { NetworkCredentials } from '@/types/wifi'
import back_axios from '@/utils/api'

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
  },
  data() {
    return {
      inputed_ssid: wifi.hotspot_credentials?.ssid || '',
      inputed_password: wifi.hotspot_credentials?.password || '',
      enable_smart_hotspot: wifi.smart_hotspot_status || false,
      selected_hotspot_interface: wifi.hotspot_interface,
      saving_settings: false,
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    interfaces(): string[] {
      return wifi.interfaces
    },
  },
  watch: {
    show(value: boolean): void {
      if (value) {
        this.selected_hotspot_interface = wifi.hotspot_interface
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
          url: `${wifi.API_URL}/hotspot_credentials`,
          data: credentials,
          timeout: 20000,
        })
          .then(() => {
            notifier.pushSuccess('HOTSPOT_CREDENTIALS_UPDATE_SUCCESS', t`Successfully updated hotspot credentials.`)
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
            notifier.pushSuccess('SMART_HOTSPOT_TOGGLE_SUCCESS', t`Successfully updated smart-hotspot configuration.`)
          })
          .catch((error) => {
            notifier.pushBackError('SMART_HOTSPOT_TOGGLE_FAIL', error, true)
          })
        const hotspot_interface = this.selected_hotspot_interface
        if (hotspot_interface !== null && hotspot_interface !== wifi.hotspot_interface) {
          await back_axios({
            method: 'post',
            url: `${wifi.API_URL}/hotspot_interface`,
            params: { interface: hotspot_interface },
            // Moving the hotspot restarts it, which can take a while
            timeout: 60000,
          })
            .then(() => {
              wifi.setHotspotInterface(hotspot_interface)
              notifier.pushSuccess('HOTSPOT_INTERFACE_UPDATE_SUCCESS', t`Successfully updated hotspot interface.`)
            })
            .catch((error) => {
              notifier.pushBackError('HOTSPOT_INTERFACE_UPDATE_FAIL', error, true)
            })
        }
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
  },
})
</script>
