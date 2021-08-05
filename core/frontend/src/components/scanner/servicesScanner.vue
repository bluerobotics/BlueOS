<template>
  <span />
</template>

<script lang="ts">
import { Service } from '@/types/SERVICE'
import ServicesScannerStore from '@/store/servicesScanner'
import Vue from 'vue'
import axios from 'axios'
import { getModule } from 'vuex-module-decorators'

const servicesHelper: ServicesScannerStore = getModule(ServicesScannerStore)

/**
 * Actual scanner for running services.
 * This periodically fetches /helper/latest/web_services
 * and updates the ServiceHelperStore with the available services
 * @displayName Services Scanner
 */
export default Vue.extend({
  name: 'ServicesFetcher',
  data () {
    return {
      // IntervalId is a number (id) returned by setInterval()
      intervalId: 0,
    }
  },
  mounted () {
    // Fetch network data
    this.requestData()

    // Fetch periodic API request
    this.startPeriodicRequest()
  },
  beforeDestroy () {
    clearInterval(this.intervalId)
  },
  methods: {
    startPeriodicRequest () {
      this.intervalId = setInterval(() => {
        this.requestData()
      }, 5000)
    },
    requestData () {
      axios.get('/helper/latest/web_services').then((response) => {
        // Sort services by port number
        const services = response.data.sort(
          (first: Service, second: Service) => first.port - second.port,
        )
        servicesHelper.updateFoundServices(services)
      }).catch((error) => {
        console.log('Error scanning for services:', error)
        servicesHelper.updateFoundServices([])
      })
    },
  },
})
</script>