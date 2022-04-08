<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import nmea_injector from '@/store/nmea-injector'
import { nmea_injector_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

const notifier = new Notifier(nmea_injector_service)

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
          notifier.pushBackError('BRIDGES_FETCH_FAIL', error)
        })
        .finally(() => {
          nmea_injector.setUpdatingNMEASockets(false)
        })
    },
  },
})
</script>
