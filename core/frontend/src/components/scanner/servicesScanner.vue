<template>
  <span />
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import notifications from '@/store/notifications'
import services_scanner from '@/store/servicesScanner'
import { service_scanner_service } from '@/types/frontend_services'
import { Service } from '@/types/helper'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

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
      axios.get('/helper/latest/web_services').then((response) => {
        // Sort services by port number
        const services = response.data.sort(
          (first: Service, second: Service) => first.port - second.port,
        )
        services_scanner.updateFoundServices(services)
      }).catch((error) => {
        services_scanner.updateFoundServices([])

        notifications.pushNotification(new LiveNotification(
          NotificationLevel.Error,
          service_scanner_service,
          'SERVICE_SCAN_FAIL',
          `Error scanning for services: ${error}`,
        ))
      })
    },
  },
})
</script>
