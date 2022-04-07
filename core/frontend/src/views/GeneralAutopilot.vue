<template>
  <v-card
    class="main-manager"
  >
    <v-card-title>Autopilot</v-card-title>
    <v-card-text>
      <span v-if="board_undefined">No board running</span>
      <div v-else>
        <span class="font-weight-bold">Board name: </span>
        <span>{{ current_board.name }}</span>
        <br>
        <span class="font-weight-bold">Manufacturer: </span>
        <span>{{ current_board.manufacturer }}</span>
        <br>
        <span class="font-weight-bold">Mavlink platform: </span>
        <span>{{ current_board.platform }}</span>
        <br>
        <span
          v-if="current_board.path"
          class="font-weight-bold"
        >
          Path:
        </span>
        <span>{{ current_board.path }}</span>
        <br>
      </div>
    </v-card-text>
    <v-card-actions class="d-flex justify-end align-center flex-wrap">
      <v-spacer />
      <v-btn
        color="blue lighten-3"
        class="ma-1"
        :disabled="restarting"
        @click="openBoardChangeDialog"
      >
        Change board
      </v-btn>
      <v-btn
        v-if="settings.is_pirate_mode"
        class="ma-1"
        color="red lighten-3"
        :disabled="restarting"
        @click="start_autopilot"
      >
        Start autopilot
      </v-btn>
      <v-btn
        v-if="settings.is_pirate_mode"
        class="ma-1"
        color="red lighten-3"
        :disabled="restarting"
        @click="stop_autopilot"
      >
        Stop autopilot
      </v-btn>
      <v-btn
        color="red lighten-3"
        class="ma-1"
        :disabled="restarting"
        @click="restart_autopilot"
      >
        Restart autopilot
      </v-btn>
    </v-card-actions>
    <board-change-dialog
      v-model="show_board_change_dialog"
    />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import BoardChangeDialog from '@/components/autopilot/BoardChangeDialog.vue'
import settings from '@/libs/settings'
import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { FlightController } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

export default Vue.extend({
  name: 'GeneralAutopilot',
  components: {
    BoardChangeDialog,
  },
  data() {
    return {
      settings,
      show_board_change_dialog: false,
    }
  },
  computed: {
    current_board(): FlightController | null {
      return autopilot.current_board
    },
    board_undefined(): boolean {
      return this.current_board === null
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
          const message = error.response.data.detail ?? error.message
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
          const message = error.response.data.detail ?? error.message
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
        timeout: 10000,
      })
        .catch((error) => {
          const message = error.response.data.detail ?? error.message
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_RESTART_FAIL', message })
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    openBoardChangeDialog(): void {
      this.show_board_change_dialog = true
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
