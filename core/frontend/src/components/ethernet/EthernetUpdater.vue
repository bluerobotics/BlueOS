<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import ethernet from '@/store/ethernet'
import notifications from '@/store/notifications'
import { ethernet_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

export default Vue.extend({
  name: 'EthernetUpdater',
  async mounted() {
    await callPeriodically(this.fetchAvailableInterfaces, 5000)
  },
  methods: {
    async fetchAvailableInterfaces(): Promise<void> {
      await axios({
        method: 'get',
        url: `${ethernet.API_URL}/ethernet`,
        timeout: 5000,
      })
        .then((response) => {
          ethernet.setInterfaces(response.data)
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            ethernet_service,
            'ETHERNET_AVAILABLE_FETCH_FAIL',
            `Could not fetch for available ethernet interfaces: ${error.message}`,
          ))
          ethernet.setInterfaces([])
        })
    },
  },
})
</script>
