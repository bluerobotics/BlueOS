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

        <v-card-actions class="flex-column d-flex justify-space-around mb-6">
          <v-btn
            class="ma-2"
            @click="reset_settings"
          >
            <v-icon left>
              mdi-cog-refresh
            </v-icon>
            Reset Settings
          </v-btn>

          <v-btn
            class="ma-2"
            @click="remove_service_log_files"
          >
            <v-icon left>
              mdi-trash-can
            </v-icon>
            Remove Services Log Files
          </v-btn>

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
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import { commander_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const API_URL = '/commander/v1.0'

const notifier = new Notifier(commander_service)

export default Vue.extend({
  name: 'PowerMenu',
  data() {
    return {
      show_dialog: false,
      show_reset_dialog: false,
      settings,
    }
  },
  methods: {
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
          notifier.pushBackError('RESET_SETTINGS_FAIL', error)
        })
    },
    async remove_service_log_files(): Promise<void> {
      await back_axios({
        url: `${API_URL}/services/remove_log`,
        method: 'post',
        params: {
          i_know_what_i_am_doing: true,
        },
        timeout: 2000,
      })
        .catch((error) => {
          notifier.pushBackError('REMOVE_SERVICES_LOG_FAIL', error)
        })
      this.showDialog(false)
    },
    showDialog(state: boolean): void {
      this.show_dialog = state
    },
  },
})
</script>
