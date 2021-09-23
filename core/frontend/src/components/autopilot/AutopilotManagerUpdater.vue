<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import AutopilotManagerStore from '@/store/autopilot_manager'
import NotificationStore from '@/store/notifications'
import { Platform } from '@/types/autopilot'
import { autopilot_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

const notification_store: NotificationStore = getModule(NotificationStore)
const autopilot_manager_store: AutopilotManagerStore = getModule(AutopilotManagerStore)

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
        url: `${autopilot_manager_store.API_URL}/endpoints`,
        timeout: 10000,
      })
        .then((response) => {
          const available_endpoints = response.data
          autopilot_manager_store.setAvailableEndpoints(available_endpoints)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_manager_service,
            'AUTOPILOT_ENDPOINT_FETCH_FAIL',
            `Could not fetch available MAVLink endpoints: ${error.message}`,
          ))
          autopilot_manager_store.setAvailableEndpoints([])
        })
    },
    async fetchCurrentPlatform(): Promise<void> {
      await axios({
        method: 'get',
        url: `${autopilot_manager_store.API_URL}/platform`,
        timeout: 10000,
      })
        .then((response) => {
          autopilot_manager_store.setCurrentPlatform(response.data)
        })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_manager_service,
            'AUTOPILOT_PLATFORM_FETCH_FAIL',
            `Could not fetch current Autopilot platform: ${error.message}`,
          ))
          autopilot_manager_store.setCurrentPlatform(Platform.Undefined)
        })
    },
  },
})
</script>
