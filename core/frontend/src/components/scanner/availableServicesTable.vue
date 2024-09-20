<template>
  <v-col>
    <v-alert
      border="top"
      colored-border
      type="info"
      elevation="2"
    >
      Shows all available services running on BlueOS, including the service port,
      name, webpage, REST API endpoint, and swagger documentation per version.

      API endpoint links provide direct manual access to the APIs, and can be used
      to test how a service responds to a given request.
    </v-alert>
    <v-simple-table class="helper-table">
      <thead>
        <tr>
          <th>Port</th>
          <th>Service Name</th>
          <th>Webpage</th>
          <th>API Documentation</th>
          <th>Versions</th>
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
              :href="service?.path ?? createWebpageUrl(service.port)"
              target="_blank"
            >
              {{ service?.path ?? createWebpageUrl(service.port) }}
            </a>
          </td>
          <td v-if="service.documentation_url">
            <a
              text
              :href="createWebpageUrl(service.port, service.documentation_url)"
              target="_blank"
            >
              {{ createWebpageUrl(service.port, service.documentation_url) }}
            </a>
          </td>
          <td v-else>
            No API documentation
          </td>
          <td v-if="!service.versions.isEmpty()">
            <div
              v-for="version in service.versions"
              :key="service.port + '-' + version"
            >
              <a
                text
                :href="createWebpageUrl(service.port, version)"
                target="_blank"
              >
                {{ version }}
              </a>
            </div>
          </td>
          <td v-else>
            No versions
          </td>
        </tr>
      </tbody>
    </v-simple-table>
  </v-col>
</template>

<script lang="ts">
import Vue from 'vue'

import helper from '@/store/helper'
import { Service } from '@/types/helper'

/**
 * Display all scanned services info as a pretty table.
 * @displayName Services Scanner Table
 */
export default Vue.extend({
  name: 'AvailableServicesTable',
  computed: {
    availableServices() {
      return helper.services.sort((a: Service, b: Service) => a.title.localeCompare(b.title))
    },
  },

  methods: {
    /**
     * Generates a url at the current host but different port and path.
     * e.g. http://[currenthost]:[newport]/[newpath]
     */
    createWebpageUrl(port: number, path = ''): string {
      return `${window.location.protocol}//${window.location.hostname}:${port}${path}`
    },
  },
})
</script>

<style scoped>
.helper-table {
    max-width: 100%;
    margin: auto;
}
</style>
