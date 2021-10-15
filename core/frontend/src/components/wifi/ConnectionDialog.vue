<template>
  <v-dialog
    width="300"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        {{ real_ssid }}

        <v-spacer />

        <v-btn
          icon
          @click="toggleInfoShow()"
        >
          <v-icon>{{ show_more_info_icon }}</v-icon>
        </v-btn>
      </v-card-title>

      <v-expand-transition>
        <div v-show="show_more_info">
          <v-card-text>
            <v-simple-table
              dense
            >
              <template #default>
                <tbody>
                  <tr
                    v-for="(value, name) in network"
                    :key="name"
                  >
                    <td>{{ name }}</td>
                    <td>{{ value }}</td>
                  </tr>
                </tbody>
              </template>
            </v-simple-table>
          </v-card-text>
        </div>
      </v-expand-transition>

      <v-card-actions class="d-flex flex-column">
        <v-container>
          <v-row>
            <v-text-field
              v-if="is_hidden"
              v-model="inputed_ssid"
              label="SSID"
              hide-details="auto"
              class="pa-2"
            />
          </v-row>

          <v-row>
            <v-card
              v-if="!show_password_input_box"
              elevation="0"
              @click="toggleForcePassword()"
            >
              <v-card-text>
                Force new password
              </v-card-text>
            </v-card>
            <password-input
              v-if="show_password_input_box"
              v-model="password"
              @submit="connectToWifiNetwork"
            />
          </v-row>

          <v-row
            class="d-flex justify-space-around py-4"
          >
            <v-btn
              v-if="network.saved"
              dark
              color="red lighten-1"
              depressed
              @click="removeSavedWifiNetwork"
            >
              Forget
            </v-btn>

            <v-btn
              dark
              color="blue darken-1"
              depressed
              @click="connectToWifiNetwork"
            >
              Connect
            </v-btn>
          </v-row>
        </v-container>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import axios from 'axios'
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationsStore from '@/store/notifications'
import WifiStore from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { Network, NetworkCredentials } from '@/types/wifi'

import PasswordInput from '../common/PasswordInput.vue'

const notification_store: NotificationsStore = getModule(NotificationsStore)
const wifi_store: WifiStore = getModule(WifiStore)

export default Vue.extend({
  name: 'ConnectionDialog',
  components: {
    PasswordInput,
  },
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    network: {
      type: Object as PropType<Network>,
      required: true,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      password: '',
      force_password: false,
      inputed_ssid: 'HIDDEN SSID',
      show_more_info: false,
    }
  },
  computed: {
    show_more_info_icon(): string {
      return this.show_more_info ? 'mdi-chevron-up' : 'mdi-information'
    },
    real_ssid(): string {
      return this.is_hidden ? this.inputed_ssid : this.network.ssid
    },
    is_hidden(): boolean {
      return this.network.ssid === null || this.network.ssid === ''
    },
    show_password_input_box(): boolean {
      if (this.force_password) {
        return true
      }
      if (this.network.saved || !this.network.locked) {
        return false
      }
      return true
    },
  },
  methods: {
    toggleInfoShow(): void {
      this.show_more_info = !this.show_more_info
    },
    toggleForcePassword(): void {
      this.force_password = !this.force_password
    },
    async connectToWifiNetwork(): Promise<void> {
      const credentials: NetworkCredentials = { ssid: this.real_ssid, password: this.password }
      await axios({
        method: 'post',
        url: `${wifi_store.API_URL}/connect`,
        timeout: 2000,
        data: credentials,
        params: { hidden: this.is_hidden },
      })
        .then(() => {
          wifi_store.setNetworkStatus(null)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            wifi_service,
            'WIFI_CONNECT_FAIL',
            `Could not connect to wifi network: ${error.message}.`,
          ))
        })
        .finally(() => {
          this.password = ''
          this.showDialog(false)
        })
    },
    async removeSavedWifiNetwork(): Promise<void> {
      await axios({
        method: 'post',
        url: `${wifi_store.API_URL}/remove`,
        timeout: 10000,
        params: { ssid: this.network.ssid },
      })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            wifi_service,
            'WIFI_FORGET_FAIL',
            `Could not remove saved wifi network: ${error.message}.`,
          ))
        })
        .finally(() => {
          this.showDialog(false)
        })
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>

<style>
</style>
