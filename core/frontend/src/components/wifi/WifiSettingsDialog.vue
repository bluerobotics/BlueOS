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
          <v-select
            v-model="inputed_country"
            v-tooltip="t`Regulatory region of the whole radio, hotspot included. Defines allowed channels and power.`"
            :items="country_options"
            :loading="loading_countries"
            :disabled="countries_unavailable"
            :error-messages="countries_unavailable ? t`Could not load the countries.` : []"
            :label="t`Regulatory country`"
            :hint="t`Changing the country can briefly drop the wifi connection.`"
            persistent-hint
            hide-details="auto"
            @change="country_picked = true"
          />
          <v-divider class="my-4" />

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
import { Country, NetworkCredentials } from '@/types/wifi'
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
      inputed_country: null as string | null,
      country_picked: false,
      country: null as string | null,
      countries: [] as Country[],
      loading_countries: false,
      saving_settings: false,
    }
  },
  computed: {
    countries_unavailable(): boolean {
      return !this.loading_countries && !this.countries.length
    },
    country_options(): { text: string, value: string }[] {
      return this.countries.map(({ name, code, max_power_dbm }) => {
        // Codes missing from the country names table have the code as their name
        const label = name === code ? code : `${name} (${code})`
        const is_default = code === '00'
        let text = label
        if (max_power_dbm > 0) {
          text = is_default
            ? t`${label} - up to ${max_power_dbm} dBm (default)`
            : t`${label} - up to ${max_power_dbm} dBm`
        } else if (is_default) {
          text = t`${label} (default)`
        }
        return { text, value: code }
      })
    },
    form(): VForm {
      return this.$refs.form as VForm
    },
  },
  watch: {
    show(opened: boolean): void {
      if (opened) {
        // data() runs before the store is populated, and reopening deliberately drops any unsaved edit
        this.inputed_ssid = wifi.hotspot_credentials?.ssid || ''
        this.inputed_password = wifi.hotspot_credentials?.password || ''
        this.enable_smart_hotspot = wifi.smart_hotspot_status || false
        // An unsaved pick from the last time it was open must not stay
        this.inputed_country = this.country
        this.country_picked = false
        this.fetchCountries()
      }
    },
  },
  methods: {
    async fetchCountries(): Promise<void> {
      this.loading_countries = true
      try {
        await Promise.all([
          back_axios({
            method: 'get',
            url: `${wifi.API_URL}/country`,
            timeout: 10000,
          })
            .then((response) => {
              // A slow answer must not overwrite what the user already picked
              if (!this.country_picked) {
                this.inputed_country = response.data.code
              }
              this.country = response.data.code
            })
            .catch((error) => {
              notifier.pushBackError('WIFI_COUNTRY_FETCH_FAIL', error)
            }),
          // The list does not change, so it is only fetched again if the last attempt failed
          this.countries.length
            ? Promise.resolve()
            : back_axios({
              method: 'get',
              url: `${wifi.API_URL}/countries`,
              timeout: 10000,
            })
              .then((response) => {
                this.countries = response.data
              })
              .catch((error) => {
                notifier.pushBackError('WIFI_COUNTRIES_FETCH_FAIL', error)
              }),
        ])
      } finally {
        this.loading_countries = false
      }
    },
    async saveSettings(): Promise<boolean> {
      if (!this.form.validate()) {
        return false
      }
      this.saving_settings = true
      try {
        // Before the hotspot restart, so the new regulatory domain is not applied under the freshly started AP
        const country = this.inputed_country
        if (country !== null && country !== this.country) {
          await back_axios({
            method: 'post',
            url: `${wifi.API_URL}/country`,
            params: { code: country },
            timeout: 10000,
          })
            .then(() => {
              this.country = country
              notifier.pushSuccess('WIFI_COUNTRY_UPDATE_SUCCESS', t`Successfully updated the regulatory country.`)
              // Setting a country also unblocks the radio, so the banner must not keep showing the old state
              return back_axios({ method: 'get', url: `${wifi.API_URL}/rfkill`, timeout: 10000 })
                .then((response) => wifi.setRfkillStatus(response.data))
                // The banner catches up on the next menu open, and the save itself already worked
                .catch(() => undefined)
            })
            .catch((error) => {
              notifier.pushBackError('WIFI_COUNTRY_UPDATE_FAIL', error, true)
              // The hotspot is not saved after a refused country, so one click does not end in mixed results
              throw error
            })
        }
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
