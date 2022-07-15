<template>
  <span />
</template>

<script lang="ts">
import { AxiosResponse } from 'axios'
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { callPeriodically } from '@/utils/helper_functions'

const notifier = new Notifier(autopilot_service)

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
          notifier.pushBackError('AUTOPILOT_ENDPOINT_FETCH_FAIL', error)
        })
    },
    async fetchAvailableBoards(): Promise<void> {
      try {
        const response: AxiosResponse = await back_axios({
          method: 'get',
          url: `${autopilot.API_URL}/available_boards`,
          timeout: 10000,
        })
        autopilot.setAvailableBoards(response.data)
      } catch (error) {
        autopilot.setAvailableBoards([])
        notifier.pushBackError('AUTOPILOT_BOARDS_FETCH_FAIL', error)
      }
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
          notifier.pushBackError('AUTOPILOT_BOARD_FETCH_FAIL', error)
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
        notifier.pushBackError('AUTOPILOT_FIRM_INFO_FETCH_FAIL', error)
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
        notifier.pushBackError('AUTOPILOT_VEHICLE_TYPE_FETCH_FAIL', error)
      }
    },
  },
})
</script>
