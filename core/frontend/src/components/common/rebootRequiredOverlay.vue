<template>
  <v-overlay
    v-if="reboot_required"
    :absolute="true"
    :opacity="0.7"
  >
    <div class="d-flex flex-column justify-center align-center">
      <p class="text-center">
        An autopilot Reboot is required.
      </p>
      <v-btn
        class="ml-auto mr-auto"
        color="primary"
        @click="rebootVehicle()"
      >
        Reboot Autopilot
      </v-btn>
    </div>
  </v-overlay>
</template>

<script lang="ts">
import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import autopilot_data from '@/store/autopilot'

export default {
  name: 'RebootRequiredOverlay',
  computed: {
    reboot_required(): boolean {
      return autopilot_data.reboot_required
    },
  },
  methods: {
    rebootVehicle() {
      AutopilotManager.restart()
    },
  },
}
</script>
