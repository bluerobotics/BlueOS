<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import bridget from '@/store/bridget'
import notifications from '@/store/notifications'
import { bridget_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { callPeriodically } from '@/utils/helper_functions'

/**
 * Responsible for updating bridget-related data.
 * This component periodically fetches external APIs to gather information
 * related to bridget functions, like bridges.
 * @displayName Bridget Updater
 */

export default Vue.extend({
  name: 'BridgetUpdater',
  async mounted() {
    await callPeriodically(this.fetchAvailableBridges, 5000)
    await callPeriodically(this.fetchAvailableSerialPorts, 5000)
  },
  methods: {
    async fetchAvailableBridges(): Promise<void> {
      axios({
        method: 'get',
        url: `${bridget.API_URL}/bridges`,
        timeout: 10000,
      })
        .then((response) => {
          const available_bridges = response.data
          bridget.setAvailableBridges(available_bridges)
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            bridget_service,
            'BRIDGES_FETCH_FAIL',
            `Could not fetch available bridges: ${error.message}`,
          ))
          bridget.setAvailableBridges([])
        })
        .finally(() => {
          bridget.setUpdatingBridges(false)
        })
    },
    async fetchAvailableSerialPorts(): Promise<void> {
      axios({
        method: 'get',
        url: `${bridget.API_URL}/serial_ports`,
        timeout: 10000,
      })
        .then((response) => {
          const available_ports = response.data
          bridget.setAvailableSerialPorts(available_ports)
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            bridget_service,
            'BRIDGET_SERIAL_PORTS_FETCH_FAIL',
            `Could not fetch available serial ports: ${error.message}`,
          ))
          bridget.setAvailableSerialPorts([])
        })
        .finally(() => {
          bridget.setUpdatingSerialPorts(false)
        })
    },
  },
})
</script>
