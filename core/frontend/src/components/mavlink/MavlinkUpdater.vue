<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink from '@/store/mavlink'

export default Vue.extend({
  name: 'MavlinkUpdater',
  mounted() {
    mavlink.setMessageRefreshRate({ messageName: 'HEARTBEAT', refreshRate: 0 })
    mavlink.setMessageRefreshRate({ messageName: 'SYS_STATUS', refreshRate: 3 })
  },
})
</script>
