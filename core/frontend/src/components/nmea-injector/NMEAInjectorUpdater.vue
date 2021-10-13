<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import NMEAInjectorStore from '@/store/nmea-injector'
import NotificationStore from '@/store/notifications'
import { nmea_injector_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

const notification_store: NotificationStore = getModule(NotificationStore)
const nmea_injector_store: NMEAInjectorStore = getModule(NMEAInjectorStore)

/**
 * Responsible for updating NMEA sockets.
 * This component periodically fetches NMEA Injector API to gather information
 * related to NMEA sockets.
 * @displayName NMEA Injector Updater
 */

export default Vue.extend({
  name: 'NMEAInjectorUpdater',
  async mounted() {
    await callPeriodically(this.fetchAvailableNMEASockets, 5000)
  },
  methods: {
    async fetchAvailableNMEASockets(): Promise<void> {
      axios({
        method: 'get',
        url: `${nmea_injector_store.API_URL}/socks`,
        timeout: 10000,
      })
        .then((response) => {
          const available_nmea_sockets = response.data
          nmea_injector_store.setAvailableNMEASockets(available_nmea_sockets)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            nmea_injector_service,
            'BRIDGES_FETCH_FAIL',
            `Could not fetch available bridges: ${error.message}`,
          ))
          nmea_injector_store.setAvailableNMEASockets([])
        })
        .finally(() => {
          nmea_injector_store.setUpdatingNMEASockets(false)
        })
    },
  },
})
</script>
