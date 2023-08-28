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

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'

export default Vue.extend({
  name: 'VehicleRebootMenu',
  methods: {
    async rebootVehicle(): Promise<void> {
      await AutopilotManager.restart()
    },
  },
})
</script>
