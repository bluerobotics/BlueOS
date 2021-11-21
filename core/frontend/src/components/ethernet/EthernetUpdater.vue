<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import ethernet from '@/store/ethernet'
import notifications from '@/store/notifications'
import { ethernet_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'EthernetUpdater',
  mounted() {
    callPeriodically(this.fetchAvailableInterfaces, 5000)
  },
  methods: {
    async fetchAvailableInterfaces(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${ethernet.API_URL}/ethernet`,
        timeout: 5000,
      })
        .then((response) => {
          ethernet.setInterfaces(response.data)
        })
        .catch((error) => {
          ethernet.setInterfaces([])
          if (error === backend_offline_error) { return }
          const message = `Could not fetch for available ethernet interfaces: ${error.message}`
          notifications.pushError({ service: ethernet_service, type: 'ETHERNET_AVAILABLE_FETCH_FAIL', message })
        })
    },
  },
})
</script>
