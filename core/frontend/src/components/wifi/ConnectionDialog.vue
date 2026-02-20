<template>
  <v-dialog
    width="350"
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
              v-if="!show_password_input_box && is_secure"
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
              color="error"
              depressed
              @click="removeSavedWifiNetwork"
            >
              Forget
            </v-btn>

            <v-btn
              dark
              color="primary"
              depressed
              :disabled="connection_status === ConnectionStatus.Connecting"
              @click="connectToWifiNetwork"
            >
              Connect
            </v-btn>
          </v-row>
        </v-container>
      </v-card-actions>
      <v-card-text v-if="connecting">
        Connecting to network, please wait...
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
import Vue, { PropType } from 'vue'

import Notifier from '@/libs/notifier'
import wifi from '@/store/wifi'
import { getErrorMessage } from '@/types/common'
import { wifi_service } from '@/types/frontend_services'
import { Network, NetworkCredentials } from '@/types/wifi'
import back_axios from '@/utils/api'

import PasswordInput from '../common/PasswordInput.vue'

enum ConnectionStatus {
  NotStarted,
  Connecting,
  Succeeded,
  Failed
}

const notifier = new Notifier(wifi_service)

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
      ConnectionStatus,
      password: '',
      force_password: false,
      inputed_ssid: 'HIDDEN SSID',
      show_more_info: false,
      connection_status: ConnectionStatus.NotStarted,
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
    is_secure(): boolean {
      return this.network.locked
    },
    connecting(): boolean {
      return this.connection_status === ConnectionStatus.Connecting
    },
  },
  watch: {
    show(val: boolean): void {
      if (val === false) {
        this.connection_status = ConnectionStatus.NotStarted
        this.password = ''
        this.force_password = false
      }
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
      this.connection_status = ConnectionStatus.Connecting
      try {
        wifi.setLoading(true)
        await back_axios({
          method: 'post',
          url: `${wifi.API_URL}/connect`,
          timeout: 50000,
          data: credentials,
          params: { hidden: this.is_hidden },
        })
        this.showDialog(false)
        this.connection_status = ConnectionStatus.Succeeded
        notifier.pushSuccess('WIFI_CONNECT_SUCCESS', `Successfully connected to '${this.real_ssid}'`, true)
        wifi.setNetworkStatus(null)
        this.password = ''
        this.force_password = false
      } catch (error) {
        this.connection_status = ConnectionStatus.Failed
        let message = getErrorMessage(error)
        message = message.concat('\n', 'Please check if the password is correct.')
        notifier.pushError('WIFI_CONNECT_FAIL', message, true)
      }
    },
    async removeSavedWifiNetwork(): Promise<void> {
      wifi.setLoading(true)
      await back_axios({
        method: 'post',
        url: `${wifi.API_URL}/remove`,
        timeout: 10000,
        params: { ssid: this.network.ssid },
      }).then(() => {
        this.$emit('forget', this.network)
      })
        .catch((error) => {
          notifier.pushBackError('WIFI_FORGET_FAIL', error)
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
