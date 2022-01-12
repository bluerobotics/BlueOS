<template>
  <v-card
    class="main-manager"
  >
    <v-card-title>Autopilot</v-card-title>
    <v-card-subtitle>Currently running '{{ current_platform }}' </v-card-subtitle>
    <v-card-actions>
      <v-spacer />
      <v-btn
        color="blue lighten-3"
        :disabled="restarting"
        @click="togglePlatform"
      >
        {{ toggle_button_text }}
      </v-btn>
      <v-btn
        v-if="settings.is_pirate_mode"
        color="red lighten-3"
        :disabled="restarting"
        @click="start_autopilot"
      >
        Start autopilot
      </v-btn>
      <v-btn
        v-if="settings.is_pirate_mode"
        color="red lighten-3"
        :disabled="restarting"
        @click="stop_autopilot"
      >
        Stop autopilot
      </v-btn>
      <v-btn
        color="red lighten-3"
        :disabled="restarting"
        @click="restart_autopilot"
      >
        Restart autopilot
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'
import settings from '@/libs/settings'

import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { Platform } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

export default Vue.extend({
  name: 'GeneralAutopilot',
  data() {
    return {
      settings,
    }
  },
  computed: {
    current_platform(): Platform {
      return autopilot.current_platform
    },
    running_sitl(): boolean {
      return [Platform.SITL_X86, Platform.SITL_ARM].includes(this.current_platform)
    },
    platform_undefined(): boolean {
      return this.current_platform === Platform.Undefined
    },
    toggle_button_text(): string {
      return this.platform_undefined || !this.running_sitl ? 'Use SITL' : 'Use board'
    },
    restarting(): boolean {
      return autopilot.restarting
    },
  },
  methods: {
    async start_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/start`,
        timeout: 10000,
      })
        .catch((error) => {
          const message = `Could not start autopilot: ${error.message}`
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_START_FAIL', message })
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    async stop_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/stop`,
        timeout: 10000,
      })
        .catch((error) => {
          const message = `Could not stop autopilot: ${error.message}`
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_STOP_FAIL', message })
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    async restart_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/restart`,
        params: { use_sitl: !this.running_sitl },
        timeout: 10000,
      })
        .catch((error) => {
          const message = `Could not restart autopilot: ${error.message}`
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_RESTART_FAIL', message })
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    async togglePlatform(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/platform`,
        params: { use_sitl: !this.running_sitl },
        timeout: 10000,
      })
        .catch((error) => {
          const { message } = error
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_PLATFORM_TOGGLE_FAIL', message })
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
  },
})
</script>

<style scoped>
.main-manager {
    max-width: 70%;
    margin: auto;
    padding: 2%;
    margin-top: 10%;
}
</style>
