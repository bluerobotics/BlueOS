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
          color="red darken-1"
          @click="disconnectFromWifiNetwork"
        >
          Disconnect
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import axios from 'axios'
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationStore from '@/store/notifications'
import WifiStore from '@/store/wifi'
import { wifi_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { Network, WifiStatus } from '@/types/wifi.d'

const notification_store: NotificationStore = getModule(NotificationStore)
const wifi_store: WifiStore = getModule(WifiStore)

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
  },
  methods: {
    toggleInfoShow(): void {
      this.show_more_info = !this.show_more_info
    },
    async disconnectFromWifiNetwork(): Promise<void> {
      await axios({
        method: 'get',
        url: `${wifi_store.API_URL}/disconnect`,
        timeout: 10000,
      })
        .then(() => {
          wifi_store.setNetworkStatus(null)
          wifi_store.setCurrentNetwork(null)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            wifi_service,
            'WIFI_DISCONNECT_FAIL',
            `Could not disconnect from wifi network: ${error.message}.`,
          ))
        })
        .finally(() => {
          this.showDialog(false)
        })
    },
    showDialog(state: boolean): void {
      this.$emit('change', state)
    },
  },
})
</script>

<style>
</style>
