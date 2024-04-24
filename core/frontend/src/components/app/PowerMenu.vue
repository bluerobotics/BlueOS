<template>
  <v-container
    id="power-menu-button"
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
      width="fit-content"
      :value="show_dialog"
      @input="showDialog"
    >
      <v-card>
        <v-card-title class="align-center">
          Power
        </v-card-title>

        <v-divider />

        <v-container class="pa-2">
          <v-card-actions class="flex-column">
            <v-btn
              v-tooltip="'Restarts the autopilot'"
              class="ma-2"
              :loading="restarting_autopilot"
              :disabled="restarting_autopilot || non_default_status"
              @click="restartAutopilot"
            >
              <v-icon
                left
                color="orange"
              >
                mdi-restart
              </v-icon>
              Restart Autopilot
            </v-btn>
            <v-btn
              v-tooltip="'Restarts the core alone, should be enough in most cases'"
              class="ma-2"
              :disabled="non_default_status"
              @click="restartContainer"
            >
              <v-icon
                left
                color="orange"
              >
                mdi-folder-refresh
              </v-icon>
              {{ settings.is_pirate_mode ? "Restart Core container" : "Soft restart" }}
            </v-btn>
            <v-btn
              v-tooltip="'Fully restarts the onboard computer'"
              class="ma-2"
              :disabled="non_default_status"
              @click="reboot"
            >
              <v-icon
                left
                color="orange"
              >
                mdi-restart-alert
              </v-icon>
              Reboot
            </v-btn>
            <v-btn
              v-tooltip="'Shuts down the onboard computer'"
              class="ma-2"
              :disabled="non_default_status"
              @click="poweroff"
            >
              <v-icon
                left
                color="red"
              >
                mdi-power-standby
              </v-icon>
              Power off
            </v-btn>
          </v-card-actions>
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
import Vue from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import settings from '@/libs/settings'
import autopilot from '@/store/autopilot_manager'
import commander from '@/store/commander'
import { ShutdownType } from '@/types/commander'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'

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
      settings,
      service_status: Status.None,
      show_dialog: false,
    }
  },
  computed: {
    restarting_autopilot(): boolean {
      return autopilot.restarting
    },
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
    async restartAutopilot(): Promise<void> {
      await AutopilotManager.restart()
    },
    async reboot(): Promise<void> {
      this.service_status = Status.Rebooting
      commander.shutdown(ShutdownType.Reboot)
      // Let wait a bit before starting to check
      setTimeout(this.waitForBackendToBeOnline, 15000)
    },
    async restartContainer(): Promise<void> {
      this.service_status = Status.Rebooting
      await back_axios({
        method: 'post',
        url: '/version-chooser/v1.0/version/restart',
      }).finally(() => setTimeout(this.waitForBackendToBeOnline, 15000))
    },
    async poweroff(): Promise<void> {
      this.service_status = Status.PoweringOff
      commander.shutdown(ShutdownType.PowerOff)
      this.waitForShutdown()
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
      back_axios({
        method: 'get',
        url: '/helper/latest/web_services',
      })
        .then(() => {
          // reload(true) forces the browser to fetch the page again
          setTimeout(() => { window.location.reload() }, 1000)
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
