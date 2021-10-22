<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { Platform } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import { callPeriodically } from '@/utils/helper_functions'

/**
 * Responsible for updating autopilot-manager-related data.
 * This component periodically fetches external APIs to gather information
 * related to autopilot-manager functions, like mavlink endpoints.
 * @displayName Autopilot Updater
 */

export default Vue.extend({
  name: 'AutopilotManagerUpdater',
  async mounted() {
    await callPeriodically(this.fetchAvailableEndpoints, 5000)
    await callPeriodically(this.fetchCurrentPlatform, 5000)
  },
  methods: {
    async fetchAvailableEndpoints(): Promise<void> {
      await axios({
        method: 'get',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
      })
        .then((response) => {
          const available_endpoints = response.data
          autopilot.setAvailableEndpoints(available_endpoints)
        })
        .catch((error) => {
          const message = `Could not fetch available MAVLink endpoints: ${error.message}`
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_ENDPOINT_FETCH_FAIL', message })
          autopilot.setAvailableEndpoints([])
        })
    },
    async fetchCurrentPlatform(): Promise<void> {
      await axios({
        method: 'get',
        url: `${autopilot.API_URL}/platform`,
        timeout: 10000,
      })
        .then((response) => {
          autopilot.setCurrentPlatform(response.data)
        })
        .catch((error) => {
          const message = `Could not fetch current Autopilot platform: ${error.message}`
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_PLATFORM_FETCH_FAIL', message })
          autopilot.setCurrentPlatform(Platform.Undefined)
        })
    },
  },
})
</script>
