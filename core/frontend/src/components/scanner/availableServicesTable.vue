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
        <td v-html="createWebpageHyperlink(service.port)" />
        <td
          v-if="service.documentation_url"
          v-html="createWebpageHyperlink(service.port, service.documentation_url)"
        />
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

  methods: {
    /**
     * Turns a url into proper <a> tags
     */
    createUrlHyperlink (url: string): string {
      return `<a href='${url}'>${url}</a>`
    },
    /**
     * Generates a url at the current host but different port and path.
     * e.g. http://[currenthost]:[newport]/[newpath]
     */
    createWebpageUrl (port: number, path = ''): string {
      return `${window.location.protocol}//${
        window.location.host.split(':')[0]
      }:${port}${path}`
    },
    /**
     * Creates a clickable <a> tag from a service port number and path
     */
    createWebpageHyperlink (port: number, path = ''): string {
      return this.createUrlHyperlink(this.createWebpageUrl(port, path))
    },
  },
  computed: {
    availableServices () {
      return servicesHelperStore.services
    },
  },
})
</script>

<style scoped>
.helper-table {
    max-width: 70%;
    margin: auto;
}
</style>
