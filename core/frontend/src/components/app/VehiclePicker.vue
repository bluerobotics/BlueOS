<template>
  <div class="vehicle-picker">
    <v-btn
      :loading="loading"
      class="mx-1"
      fab
      dark
      x-small
      @click="toggleDropdown"
    >
      <v-icon>{{ expanded ? 'mdi-chevron-up' : 'mdi-chevron-down' }}</v-icon>
    </v-btn>

    <v-menu
      v-model="expanded"
      :close-on-content-click="false"
      offset-y
      min-width="150"
    >
      <template #activator="{ }" />

      <v-card>
        <v-card-title class="subtitle-2 pa-2">
          Other Vehicles detected on your network
          <v-spacer />
          <v-btn
            icon
            x-small
            @click="refreshServices"
          >
            <v-icon small>
              mdi-refresh
            </v-icon>
          </v-btn>
        </v-card-title>

        <v-divider />

        <v-list v-if="availableVehicles.length > 0" dense>
          <v-list-item
            v-for="vehicle in availableVehicles"
            :key="vehicle.hostname"
          >
            <v-list-item-avatar>
              <v-img
                v-if="vehicle.imagePath"
                :src="vehicle.imagePath"
                :alt="vehicle.hostname"
                aspect-ratio="1"
                class="vehicle-image"
              >
                <template #error>
                  <v-icon color="primary">
                    mdi-submarine
                  </v-icon>
                </template>
              </v-img>
              <v-icon v-else color="primary">
                mdi-submarine
              </v-icon>
            </v-list-item-avatar>
            <v-list-item-content>
              <v-list-item-title>
                <span class="vehicle-name">
                  {{ vehicle.hostname }}
                </span>
                {{ allMyIps.includes(vehicle.ips[0]) ? '(This Vehicle)' : '' }}
              </v-list-item-title>
              <v-list-item-title v-for="ip in vehicle.ips" :key="ip" class="caption" @click="navigateToVehicle(ip)">
                {{ ip }}
                <v-icon x-small color="primary">
                  mdi-launch
                </v-icon>
              </v-list-item-title>
            </v-list-item-content>
          </v-list-item>
        </v-list>

        <v-card-text v-else-if="!loading" class="text-center text--secondary">
          <div v-if="error">
            <v-icon color="error">
              mdi-alert-circle
            </v-icon>
            <div class="caption">
              {{ error }}
            </div>
          </div>
          <div v-else>
            No vehicles discovered
          </div>
        </v-card-text>

        <v-card-text v-else class="text-center">
          <v-progress-circular
            indeterminate
            size="24"
            width="2"
          />
          <div class="caption mt-2">
            Discovering vehicles...
          </div>
        </v-card-text>
      </v-card>
    </v-menu>
  </div>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import system_information from '@/store/system-information'

interface DiscoveredServices {
  [ip: string]: string[]
}

interface Vehicle {
  ips: string[]
  hostname: string
  imagePath?: string
}

export default Vue.extend({
  name: 'VehiclePicker',
  data() {
    return {
      expanded: false,
      loading: false,
      error: null as string | null,
      availableVehicles: [] as Vehicle[],
    }
  },
  computed: {
    allMyIps(): string[] {
      return system_information.system?.network.flatMap((network) => network.ips.map((ip) => ip.split('/')[0])) || []
    },
  },
  methods: {
    toggleDropdown() {
      this.expanded = !this.expanded
      if (this.expanded && this.availableVehicles.length === 0) {
        this.fetchDiscoveredServices()
      }
    },

    async fetchDiscoveredServices() {
      this.loading = true
      this.error = null
      this.availableVehicles = []

      try {
        const response = await axios.get('/beacon/v1.0/discovered_services', {
          timeout: 10000,
        })

        const discoveredServices: DiscoveredServices = response.data
        const ips = Object.keys(discoveredServices)

        if (ips.length === 0) {
          this.error = 'No vehicles discovered'
          this.loading = false
          return
        }

        let completedRequests = 0

        ips.forEach(async (ip) => {
          try {
            const hostnameResponse = await axios.get(`http://${ip}/beacon/v1.0/hostname`, {
              timeout: 5000,
            })

            let imagePath: string | undefined
            try {
              const imageResponse = await axios.get(`http://${ip}/bag/v1.0/get/vehicle.image_path`, {
                timeout: 3000,
              })
              imagePath = `http://${ip}${imageResponse.data.url}`
            } catch {
              // Image not available, use fallback
            }

            const newVehicle: Vehicle = {
              ips: [ip],
              hostname: hostnameResponse.data,
              imagePath,
            }

            const existingVehicleIndex = this.availableVehicles.findIndex(
              (v) => v.hostname === newVehicle.hostname,
            )

            if (existingVehicleIndex >= 0) {
              this.availableVehicles[existingVehicleIndex].ips.push(...newVehicle.ips)
              if (newVehicle.imagePath && !this.availableVehicles[existingVehicleIndex].imagePath) {
                this.availableVehicles[existingVehicleIndex].imagePath = newVehicle.imagePath
              }
            } else {
              this.availableVehicles.push(newVehicle)
            }

            this.availableVehicles.sort((a, b) => a.hostname.localeCompare(b.hostname))
          } catch (error) {
            console.warn(`Failed to fetch hostname for ${ip}:`, error)
          } finally {
            completedRequests += 1
            if (completedRequests === ips.length) {
              this.loading = false
              if (this.availableVehicles.length === 0) {
                this.error = 'No accessible vehicles found'
              }
            }
          }
        })
      } catch (error) {
        console.error('Failed to fetch discovered services:', error)
        this.error = 'Failed to discover vehicles'
        this.availableVehicles = []
        this.loading = false
      }
    },

    async refreshServices() {
      await this.fetchDiscoveredServices()
    },

    navigateToVehicle(ip: string) {
      window.open(`http://${ip}`, '_blank')
      this.expanded = false
    },
  },
})
</script>

<style scoped>
.vehicle-picker {
  display: inline-block;
}

.caption:hover {
  background-color: rgba(0, 0, 0, 0.04);
  cursor: pointer;
}

.vehicle-image {
  border-radius: 4px;
}

.v-list-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.vehicle-name {
  font-size: 1.2rem;
}
</style>
