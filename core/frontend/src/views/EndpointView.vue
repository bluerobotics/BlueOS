<template>
  <v-container>
    <endpoint-manager />
  </v-container>
</template>

<script lang="ts">
import Vue from 'vue'

import EndpointManager from '@/components/autopilot/EndpointManager.vue'

export default Vue.extend({
  name: 'EndpointView',
  components: {
    EndpointManager,
  },
})
</script>
