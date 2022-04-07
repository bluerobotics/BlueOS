<template>
  <span />
</template>

<script lang="ts">
import { AxiosResponse } from 'axios'
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { autopilot_service } from '@/types/frontend_services'
import back_axios, { backend_offline_error } from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

/**
 * Responsible for updating autopilot-manager-related data.
 * This component periodically fetches external APIs to gather information
 * related to autopilot-manager functions, like mavlink endpoints.
 * @displayName Autopilot Updater
 */

export default Vue.extend({
  name: 'AutopilotManagerUpdater',
  mounted() {
    callPeriodically(this.fetchAvailableEndpoints, 5000)
    callPeriodically(this.fetchAvailableBoards, 5000)
    callPeriodically(this.fetchCurrentBoard, 5000)
    callPeriodically(this.fetchFirmwareInfo, 5000)
    callPeriodically(this.fetchVehicleType, 5000)
  },
  methods: {
    async fetchAvailableEndpoints(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
      })
        .then((response) => {
          const available_endpoints = response.data
          autopilot.setAvailableEndpoints(available_endpoints)
        })
        .catch((error) => {
          autopilot.setAvailableEndpoints([])
          if (error === backend_offline_error) { return }
          const message = error.response?.data?.detail ?? error.message
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_ENDPOINT_FETCH_FAIL', message })
        })
    },
    async fetchAvailableBoards(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/available_boards`,
        timeout: 10000,
      })
        .then((response) => {
          const available_boards = response.data
          autopilot.setAvailableBoards(available_boards)
        })
        .catch((error) => {
          autopilot.setAvailableBoards([])
          if (error === backend_offline_error) { return }
          const message = error.response?.data?.detail ?? error.message
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_BOARDS_FETCH_FAIL', message })
        })
    },
    async fetchCurrentBoard(): Promise<void> {
      await back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/board`,
        timeout: 10000,
      })
        .then((response) => {
          autopilot.setCurrentBoard(response.data)
        })
        .catch((error) => {
          autopilot.setCurrentBoard(null)
          if (error === backend_offline_error) { return }
          const message = error.response?.data?.detail ?? error.message
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_BOARD_FETCH_FAIL', message })
        })
    },
    async fetchFirmwareInfo(): Promise<void> {
      try {
        const response: AxiosResponse = await back_axios({
          method: 'get',
          url: `${autopilot.API_URL}/firmware_info`,
          timeout: 10000,
        })
        autopilot.setFirmwareInfo(response.data)
      } catch (error) {
        autopilot.setFirmwareInfo(null)
        if (error === backend_offline_error) { return }
        const message = error.response?.data?.detail ?? error.message
        notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_FIRM_INFO_FETCH_FAIL', message })
      }
    },
    async fetchVehicleType(): Promise<void> {
      try {
        const response: AxiosResponse = await back_axios({
          method: 'get',
          url: `${autopilot.API_URL}/vehicle_type`,
          timeout: 10000,
        })
        autopilot.setVehicleType(response.data)
      } catch (error) {
        autopilot.setVehicleType(null)
        if (error === backend_offline_error) { return }
        const message = error.response?.data?.detail ?? error.message
        notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_VEHICLE_TYPE_FETCH_FAIL', message })
      }
    },
  },
})
</script>
