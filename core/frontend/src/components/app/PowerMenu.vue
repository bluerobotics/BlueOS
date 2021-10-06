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
      width="250"
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
              @click="poweroff"
            >
              <v-icon color="red">
                mdi-power-standby
              </v-icon>
            </v-btn>
            <v-btn
              class="mr-2"
              @click="reboot"
            >
              <v-icon color="orange">
                mdi-restart-alert
              </v-icon>
            </v-btn>
          </v-row>
        </v-container>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import NotificationStore from '@/store/notifications'
import { commander_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

const notification_store: NotificationStore = getModule(NotificationStore)

const API_URL = '/commander/v1.0'

enum ShutdownType {
  Reboot = 'reboot',
  PowerOff = 'poweroff',
}

export default Vue.extend({
  name: 'PowerMenu',
  components: {
  },
  data() {
    return {
      show_dialog: false,
    }
  },
  computed: {
  },
  methods: {
    async reboot(): Promise<void> {
      this.shutdown(ShutdownType.Reboot)
    },
    async poweroff(): Promise<void> {
      this.shutdown(ShutdownType.PowerOff)
    },
    async shutdown(shutdown_type: ShutdownType): Promise<void> {
      await axios({
        url: `${API_URL}/shutdown`,
        method: 'post',
        params: {
          shutdown_type: `${shutdown_type}`,
          i_know_what_i_am_doing: true,
        },
      }).catch((error) => {
        const detail_message = 'detail' in error.response.data
          ? error.response.data.detail : ''
        notification_store.pushNotification(new LiveNotification(
          NotificationLevel.Error,
          commander_service,
          'SHUTDOWN_FAIL',
          `Failed to commit operation: ${error.message}, ${detail_message}`
          ,
        ))
      })
      this.showDialog(false)
    },
    showDialog(state: boolean): void {
      this.show_dialog = state
    },
  },
})
</script>
