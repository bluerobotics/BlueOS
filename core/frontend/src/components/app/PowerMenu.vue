<template>
  <v-container
    class="d-flex justify-center"
  >
    <v-btn
      class="mr-2"
      icon
      large
      elevation="2"
      @click="showDialog(true)"
    >
      <v-icon>mdi-power-settings</v-icon>
    </v-btn>
    <v-dialog
      width="320"
      :value="show_dialog"
      @input="showDialog"
    >
      <v-card>
        <v-card-title class="align-center">
          Shut Down
        </v-card-title>

        <v-divider />

        <v-container class="pa-8">
          <v-row
            justify="center"
          >
            <v-btn
              class="mr-2"
              :disabled="non_default_status"
              @click="poweroff"
            >
              <v-icon color="red">
                mdi-power-standby
              </v-icon>
            </v-btn>
            <v-btn
              class="mr-2"
              :disabled="non_default_status"
              @click="reboot"
            >
              <v-icon color="orange">
                mdi-restart-alert
              </v-icon>
            </v-btn>
          </v-row>
        </v-container>
        <v-container v-if="non_default_status">
          <p class="text-md-center">
            {{ service_status_text }}
          </p>
          <spinning-logo
            v-if="show_spinner"
            size="30%"
          />
        </v-container>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import notifications from '@/store/notifications'
import { commander_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

import SpinningLogo from '../common/SpinningLogo.vue'

const API_URL = '/commander/v1.0'

// Used to communicate with REST API
enum ShutdownType {
  Reboot = 'reboot',
  PowerOff = 'poweroff',
}

/// Used for internal status control
enum Status {
  None,
  Rebooting,
  PoweringOff,
  PowerOff,
}

export default Vue.extend({
  name: 'PowerMenu',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      service_status: Status.None,
      show_dialog: false,
    }
  },
  computed: {
    non_default_status(): boolean {
      return this.service_status !== Status.None
    },
    service_status_text(): string {
      switch (this.service_status) {
        case Status.Rebooting:
          return 'System is rebooting, please wait.'
        case Status.PoweringOff:
          return 'System is turning off, please wait.'
        case Status.PowerOff:
          return 'System is off. You can disconnect power now.'
        default:
          return ''
      }
    },
    show_spinner(): boolean {
      return this.service_status !== Status.None && this.service_status !== Status.PowerOff
    },
  },
  methods: {
    async reboot(): Promise<void> {
      this.service_status = Status.Rebooting
      this.shutdown(ShutdownType.Reboot)
      // Let wait a bit before starting to check
      setTimeout(this.waitForBackendToBeOnline, 5000)
    },
    async poweroff(): Promise<void> {
      this.service_status = Status.PoweringOff
      this.shutdown(ShutdownType.PowerOff)
      this.waitForShutdown()
    },
    async shutdown(shutdown_type: ShutdownType): Promise<void> {
      await axios({
        url: `${API_URL}/shutdown`,
        method: 'post',
        params: {
          shutdown_type: `${shutdown_type}`,
          i_know_what_i_am_doing: true,
        },
        timeout: 2000,
      }).catch((error) => {
        // Connection lost/timeout, normal when we are turnning off/rebooting
        if (error.code === 'ECONNABORTED') {
          return
        }

        const detail_message = 'detail' in error.response.data
          ? error.response.data.detail : ''
        notifications.pushNotification(new LiveNotification(
          NotificationLevel.Error,
          commander_service,
          'SHUTDOWN_FAIL',
          `Failed to commit operation: ${error.message}, ${detail_message}`
          ,
        ))
      })
    },
    showDialog(state: boolean): void {
      this.show_dialog = state
    },
    async waitForShutdown(): Promise<void> {
      this.service_status = Status.PoweringOff
      // Let us wait 30 seconds before saying that the system is off
      setTimeout(() => { this.service_status = Status.PowerOff }, 30000)
    },
    async waitForBackendToBeOnline(): Promise<void> {
      this.service_status = Status.Rebooting
      axios({
        method: 'get',
        url: '/helper/latest/web_services',
      })
        .then(() => {
          // reload(true) forces the browser to fetch the page again
          setTimeout(() => { window.location.reload(true) }, 1000)
        })
        .catch((error) => {
          // Backend is not available yet, check again soon
          console.debug(`Backend is not available yet: ${error}`)
          setTimeout(this.waitForBackendToBeOnline, 2000)
        })
    },
  },
})
</script>
