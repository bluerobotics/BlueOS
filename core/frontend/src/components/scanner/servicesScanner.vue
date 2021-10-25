<template>
  <span />
</template>

<script lang="ts">
import Vue from 'vue'

import notifications from '@/store/notifications'
import services_scanner from '@/store/servicesScanner'
import { service_scanner_service } from '@/types/frontend_services'
import { Service } from '@/types/helper'
import back_axios, { backend_offline_error } from '@/utils/api'

/**
 * Actual scanner for running services.
 * This periodically fetches /helper/latest/web_services
 * and updates the ServiceHelperStore with the available services
 * @displayName Services Scanner
 */
export default Vue.extend({
  name: 'ServicesFetcher',
  data() {
    return {
      // IntervalId is a number (id) returned by setInterval()
      intervalId: 0,
    }
  },
  mounted() {
    // Fetch network data
    this.requestData()

    // Fetch periodic API request
    this.startPeriodicRequest()
  },
  beforeDestroy() {
    clearInterval(this.intervalId)
  },
  methods: {
    startPeriodicRequest() {
      this.intervalId = setInterval(() => {
        this.requestData()
      }, 5000)
    },
    requestData() {
      back_axios({
        method: 'get',
        url: '/helper/latest/web_services',
        timeout: 10000,
      })
        .then((response) => {
          // Sort services by port number
          const services = response.data.sort(
            (first: Service, second: Service) => first.port - second.port,
          )
          services_scanner.updateFoundServices(services)
        })
        .catch((error) => {
          services_scanner.updateFoundServices([])
          if (error === backend_offline_error) { return }

          const message = `Error scanning for services: ${error}`
          notifications.pushError({ service: service_scanner_service, type: 'SERVICE_SCAN_FAIL', message })
        })
    },
  },
})
</script>
