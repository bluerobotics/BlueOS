<template>
  <v-simple-table class="helper-table">
    <thead>
      <tr>
        <th>Port</th>
        <th>Service Name</th>
        <th>Webpage</th>
        <th>API Documentation</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="service in availableServices"
        :key="service.port"
      >
        <td>{{ service.port }}</td>
        <td>{{ service.title }}</td>
        <td>
          <a
            :href="createWebpageUrl(service.port)"
          >
            {{ createWebpageUrl(service.port) }}
          </a>
        </td>
        <td v-if="service.documentation_url">
          <a
            text
            :href="createWebpageUrl(service.port, service.documentation_url)"
          >
            {{ createWebpageUrl(service.port, service.documentation_url) }}
          </a>
        </td>
        <td v-else>
          No API documentation
        </td>
      </tr>
    </tbody>
  </v-simple-table>
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import ServicesScannerStore from '@/store/servicesScanner'

const servicesHelperStore: ServicesScannerStore = getModule(ServicesScannerStore)

/**
 * Display all scanned services info as a pretty table.
 * @displayName Services Scanner Table
 */
export default Vue.extend({
  name: 'AvailableServicesTable',
  computed: {
    availableServices() {
      return servicesHelperStore.services
    },
  },

  methods: {
    /**
     * Generates a url at the current host but different port and path.
     * e.g. http://[currenthost]:[newport]/[newpath]
     */
    createWebpageUrl(port: number, path = ''): string {
      return `${window.location.protocol}//${
        window.location.host.split(':')[0]
      }:${port}${path}`
    },
  },
})
</script>

<style scoped>
.helper-table {
    max-width: 80%;
    margin: auto;
}
</style>
