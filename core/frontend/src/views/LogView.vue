<template>
  <log-manager />
</template>

<script lang="ts">
import Vue from 'vue'

import LogManager from '@/components/logs/LogManager.vue'

export default Vue.extend({
  name: 'LogView',
  components: {
    LogManager,
  },
})
</script>
