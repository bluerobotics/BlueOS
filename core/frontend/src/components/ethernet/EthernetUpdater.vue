<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import EthernetStore from '@/store/ethernet'
import NotificationsStore from '@/store/notifications'
import { ethernet_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

const notification_store: NotificationsStore = getModule(NotificationsStore)
const ethernet_store: EthernetStore = getModule(EthernetStore)

export default Vue.extend({
  name: 'EthernetUpdater',
  async mounted() {
    await callPeriodically(this.fetchAvailableInterfaces, 5000)
  },
  methods: {
    async fetchAvailableInterfaces(): Promise<void> {
      await axios({
        method: 'get',
        url: `${ethernet_store.API_URL}/ethernet`,
        timeout: 5000,
      })
        .then((response) => {
          ethernet_store.setInterfaces(response.data)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            ethernet_service,
            'ETHERNET_AVAILABLE_FETCH_FAIL',
            `Could not fetch for available ethernet interfaces: ${error.message}`,
          ))
          ethernet_store.setInterfaces([])
        })
    },
  },
})
</script>
