<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import MavlinkStore from '@/store/mavlink'

const mavlink_store: MavlinkStore = getModule(MavlinkStore)

export default Vue.extend({
  name: 'MavlinkUpdater',
  mounted() {
    mavlink_store.setMessageRefreshRate({ messageName: 'HEARTBEAT', refreshRate: 1 })
    mavlink_store.setMessageRefreshRate({ messageName: 'SYS_STATUS', refreshRate: 3 })
  },
})
</script>
