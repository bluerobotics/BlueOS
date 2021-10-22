<template>
  <v-card
    class="main-manager"
  >
    <v-card-title>Autopilot</v-card-title>
    <v-card-subtitle>Currently running '{{ current_platform }}' </v-card-subtitle>
    <v-card-actions>
      <v-spacer />
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
import axios from 'axios'
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { Platform } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'

export default Vue.extend({
  name: 'GeneralAutopilot',
  computed: {
    current_platform(): Platform {
      return autopilot.current_platform
    },
    restarting(): boolean {
      return autopilot.restarting
    },
  },
  methods: {
    async restart_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await axios({
        method: 'post',
        url: `${autopilot.API_URL}/restart`,
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
