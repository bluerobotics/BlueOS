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
import { getModule } from 'vuex-module-decorators'

import AutopilotManagerStore from '@/store/autopilot_manager'
import NotificationStore from '@/store/notifications'
import { Platform } from '@/types/autopilot'
import { autopilot_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

const notification_store: NotificationStore = getModule(NotificationStore)
const autopilot_manager_store: AutopilotManagerStore = getModule(AutopilotManagerStore)

export default Vue.extend({
  name: 'GeneralAutopilot',
  computed: {
    current_platform(): Platform {
      return autopilot_manager_store.current_platform
    },
    restarting(): boolean {
      return autopilot_manager_store.restarting
    },
  },
  methods: {
    async restart_autopilot(): Promise<void> {
      autopilot_manager_store.setRestarting(true)
      await axios({
        method: 'post',
        url: `${autopilot_manager_store.API_URL}/restart`,
        timeout: 10000,
      })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_manager_service,
            'AUTOPILOT_RESTART_FAIL',
            `Could not restart autopilot: ${error.message}`,
          ))
        })
        .finally(() => {
          autopilot_manager_store.setRestarting(false)
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
