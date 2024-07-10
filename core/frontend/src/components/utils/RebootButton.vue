<template>
  <v-btn
    v-if="rebootRequired"
    color="warning"
    @click="rebootVehicle"
  >
    Reboot Autopilot
  </v-btn>
</template>

<script lang="ts">
import Vue from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import autopilot_data from '@/store/autopilot'

export default Vue.extend({
  name: 'RebootButton',
  computed: {
    rebootRequired(): boolean {
      return autopilot_data.reboot_required
    },
  },
  methods: {
    async rebootVehicle(): Promise<void> {
      await AutopilotManager.restart()
    },
  },
})
</script>
