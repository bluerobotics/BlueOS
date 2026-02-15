<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title class="text-h5">
        {{ network.ssid }}

        <v-spacer />

        <v-btn
          icon
          @click="toggleInfoShow()"
        >
          <v-icon>{{ show_more_info_icon }}</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-title
        v-if="holds_ip_being_used"
        class="justify-center"
      >
        <v-icon
          color="white"
          size="45"
        >
          mdi-alert-octagon
        </v-icon>
      </v-card-title>

      <v-card-subtitle
        v-if="holds_ip_being_used"
        class="text-center mt-2 mb-2"
      >
        This IP address is currently being used to access BlueOS.
        Deleting it could prevent you from accessing your vehicle. Are you sure you want to disconnect?
      </v-card-subtitle>

      <v-expand-transition>
        <div v-show="show_more_info">
          <v-card-text>
            <v-simple-table
              dense
            >
              <template #default>
                <tbody>
                  <tr
                    v-for="(value, name) in connection_info"
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

      <v-card-actions class="d-flex flex-column py-6">
        <v-btn
          elevation="1"
          dark
          color="error"
          @click="disconnectFromWifiNetwork"
        >
          Disconnect
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import Notifier from '@/libs/notifier'
import beacon from '@/store/beacon'
import wifi from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { Network, WifiStatus } from '@/types/wifi'
import back_axios from '@/utils/api'

const notifier = new Notifier(wifi_service)

export default Vue.extend({
  name: 'DisconnectionDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    network: {
      type: Object as PropType<Network>,
      required: true,
    },
    status: {
      type: Object as PropType<WifiStatus | null>,
      required: true,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      show_more_info: false,
    }
  },
  computed: {
    show_more_info_icon(): string {
      return this.show_more_info ? 'mdi-chevron-up' : 'mdi-information'
    },
    connection_info(): Network | (Network & WifiStatus) {
      if (this.status === null) {
        return this.network
      }
      return { ...this.network, ...this.status }
    },
    holds_ip_being_used(): boolean {
      return this.status?.ip_address === beacon.nginx_ip_address
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
  },
  methods: {
    toggleInfoShow(): void {
      this.show_more_info = !this.show_more_info
    },
    async disconnectFromWifiNetwork(): Promise<void> {
      wifi.setLoading(true)
      this.showDialog(false)
      await back_axios({
        method: 'get',
        url: `${wifi.API_URL}/disconnect`,
        timeout: 10000,
      })
        .then(() => {
          wifi.setNetworkStatus(null)
          wifi.setCurrentNetwork(null)
        })
        .catch((error) => {
          const message = `Could not disconnect from wifi network: ${error.message}.`
          notifier.pushError('WIFI_DISCONNECT_FAIL', message)
        })
    },
    showDialog(state: boolean): void {
      this.$emit('change', state)
    },
  },
})
</script>
