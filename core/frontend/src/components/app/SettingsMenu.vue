<template>
  <v-container
    id="settings-menu-button"
    class="d-flex justify-center"
  >
    <v-btn
      class="mr-2"
      icon
      large
      elevation="2"
      @click="showDialog(true)"
    >
      <v-icon>mdi-cog</v-icon>
    </v-btn>
    <v-dialog
      width="320"
      :value="show_dialog"
      @input="showDialog"
    >
      <v-card>
        <v-card-title class="align-center">
          Settings
        </v-card-title>

        <v-divider />

        <v-card-actions class="d-flex flex-column justify-space-around align-center">
          <v-btn
            @click="reset_settings"
          >
            <v-icon left>
              mdi-cog-refresh
            </v-icon>
            Reset Settings
          </v-btn>
          <v-switch
            v-model="settings.is_pirate_mode"
            label="Pirate mode"
            @change="togglePirateWarning"
          />
          <v-switch
            v-model="settings.is_dark_theme"
            label="Dark mode"
          />
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog
      width="380"
      :value="show_reset_dialog"
      @input="show_reset_dialog = false"
    >
      <v-card>
        <v-container class="pa-8">
          Restart the system to finish the settings reset.
        </v-container>
      </v-card>
    </v-dialog>
    <v-dialog
      v-model="pirate_warning"
      max-width="290"
    >
      <v-card>
        <v-card-title class="text-h5">
          Pirate mode activated!
        </v-card-title>
        <v-card-text>
          With a shiny hook comes great responsibilities! If you're navigating, don't drink rum.
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import settings from '@/libs/settings'
import notifications from '@/store/notifications'
import { commander_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const API_URL = '/commander/v1.0'

export default Vue.extend({
  name: 'PowerMenu',
  data() {
    return {
      show_dialog: false,
      show_reset_dialog: false,
      settings,
      pirate_warning: false,
    }
  },
  methods: {
    togglePirateWarning(): void {
      this.pirate_warning = settings.is_pirate_mode
    },
    async reset_settings(): Promise<void> {
      await back_axios({
        url: `${API_URL}/settings/reset`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 2000,
      })
        .then(() => {
          this.show_reset_dialog = true
        })
        .catch((error) => {
          const detail_message = 'data' in error.response
            && 'message' in error.response.data ? error.response.data.message : 'No details available.'
          const message = `Failed to commit operation: ${error.message}, ${detail_message}`
          notifications.pushError({ service: commander_service, type: 'RESET_SETTINGS_FAIL', message })
        })
    },
    showDialog(state: boolean): void {
      this.show_dialog = state
    },
  },
})
</script>
