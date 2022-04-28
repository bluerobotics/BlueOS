<template>
  <div class="page">
    <endpoint-manager />
  </div>
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

<style scoped>
.page {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}
</style>
