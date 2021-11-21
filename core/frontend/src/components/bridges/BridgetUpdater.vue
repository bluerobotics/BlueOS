<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import bridget from '@/store/bridget'
import notifications from '@/store/notifications'
import { bridget_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

/**
 * Responsible for updating bridget-related data.
 * This component periodically fetches external APIs to gather information
 * related to bridget functions, like bridges.
 * @displayName Bridget Updater
 */

export default Vue.extend({
  name: 'BridgetUpdater',
  mounted() {
    callPeriodically(this.fetchAvailableBridges, 5000)
    callPeriodically(this.fetchAvailableSerialPorts, 5000)
  },
  methods: {
    async fetchAvailableBridges(): Promise<void> {
      back_axios({
        method: 'get',
        url: `${bridget.API_URL}/bridges`,
        timeout: 10000,
      })
        .then((response) => {
          const available_bridges = response.data
          bridget.setAvailableBridges(available_bridges)
        })
        .catch((error) => {
          bridget.setAvailableBridges([])
          if (error === backend_offline_error) { return }
          const message = `Could not fetch available bridges: ${error.message}`
          notifications.pushError({ service: bridget_service, type: 'BRIDGES_FETCH_FAIL', message })
        })
        .finally(() => {
          bridget.setUpdatingBridges(false)
        })
    },
    async fetchAvailableSerialPorts(): Promise<void> {
      back_axios({
        method: 'get',
        url: `${bridget.API_URL}/serial_ports`,
        timeout: 10000,
      })
        .then((response) => {
          const available_ports = response.data
          bridget.setAvailableSerialPorts(available_ports)
        })
        .catch((error) => {
          bridget.setAvailableSerialPorts([])
          if (error === backend_offline_error) { return }
          const message = `Could not fetch available serial ports: ${error.message}`
          notifications.pushError({ service: bridget_service, type: 'BRIDGET_SERIAL_PORTS_FETCH_FAIL', message })
        })
        .finally(() => {
          bridget.setUpdatingSerialPorts(false)
        })
    },
  },
})
</script>
