<template>
  <v-container>
    <firmware-manager />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import FirmwareManager from '@/components/autopilot/FirmwareManager.vue'

export default Vue.extend({
  name: 'FirmwareView',
  components: {
    FirmwareManager,
  },
})
</script>
