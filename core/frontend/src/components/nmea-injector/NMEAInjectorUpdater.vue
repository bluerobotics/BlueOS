<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import nmea_injector from '@/store/nmea-injector'
import notifications from '@/store/notifications'
import { nmea_injector_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

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
        url: `${nmea_injector.API_URL}/socks`,
        timeout: 10000,
      })
        .then((response) => {
          const available_nmea_sockets = response.data
          nmea_injector.setAvailableNMEASockets(available_nmea_sockets)
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            nmea_injector_service,
            'BRIDGES_FETCH_FAIL',
            `Could not fetch available bridges: ${error.message}`,
          ))
          nmea_injector.setAvailableNMEASockets([])
        })
        .finally(() => {
          nmea_injector.setUpdatingNMEASockets(false)
        })
    },
  },
})
</script>
