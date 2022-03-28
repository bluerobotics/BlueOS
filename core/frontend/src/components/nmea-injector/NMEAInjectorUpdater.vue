<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import nmea_injector from '@/store/nmea-injector'
import notifications from '@/store/notifications'
import { nmea_injector_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

/**
 * Responsible for updating NMEA sockets.
 * This component periodically fetches NMEA Injector API to gather information
 * related to NMEA sockets.
 * @displayName NMEA Injector Updater
 */

export default Vue.extend({
  name: 'NMEAInjectorUpdater',
  mounted() {
    callPeriodically(this.fetchAvailableNMEASockets, 5000)
  },
  methods: {
    async fetchAvailableNMEASockets(): Promise<void> {
      back_axios({
        method: 'get',
        url: `${nmea_injector.API_URL}/socks`,
        timeout: 10000,
      })
        .then((response) => {
          const available_nmea_sockets = response.data
          nmea_injector.setAvailableNMEASockets(available_nmea_sockets)
        })
        .catch((error) => {
          nmea_injector.setAvailableNMEASockets([])
          if (error === backend_offline_error) { return }
          const message = error.response.data.detail ?? error.message
          notifications.pushError({ service: nmea_injector_service, type: 'BRIDGES_FETCH_FAIL', message })
        })
        .finally(() => {
          nmea_injector.setUpdatingNMEASockets(false)
        })
    },
  },
})
</script>
