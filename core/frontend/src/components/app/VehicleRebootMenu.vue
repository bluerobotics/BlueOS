<template>
  <v-card
    class="d-flex flex-column align-center pa-3"
    outlined
    width="350"
  >
    <v-alert
      type="info"
      icon="mdi-skull-crossbones"
      elevation="1"
      text
    >
      Autopilot reboot is necessary for new settings to take effect.
    </v-alert>
    <v-btn
      @click="rebootVehicle"
    >
      Reboot Autopilot
    </v-btn>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { parameters_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(parameters_service)

export default Vue.extend({
  name: 'VehicleRebootMenu',
  methods: {
    async rebootVehicle(): Promise<void> {
      autopilot_data.reset()
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/restart`,
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_RESTART_FAIL', error)
        })
        .finally(() => {
          autopilot.setRestarting(false)
          autopilot_data.setRebootRequired(false)
        })
    },
  },
})
</script>
