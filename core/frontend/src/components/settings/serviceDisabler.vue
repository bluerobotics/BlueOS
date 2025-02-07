<template>
  <v-card flat>
    <div
      v-for="service in services"
      :key="service"
      class="service-item d-flex align-center ml-10 mr-10"
    >
      <v-switch
        v-model="states[service]"
        dense
        class="ma-0 pa-0 flex-grow-1 switch-label"
        :label="service"
        hide-details
        inset
        @change="handleServiceStateChange(service)"
      />
      <v-icon
        v-tooltip="serviceTooltips[service]"
        small
        class="ml-1 info-icon"
        color="info"
      >
        mdi-information
      </v-icon>
    </div>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import commander from '@/store/commander'
import { commander_service } from '@/types/frontend_services'
import { getVersionChooserEnvironmentVariables, setVersionChooserEnvironmentVariables } from '@/utils/version_chooser'

const notifier = new Notifier(commander_service)

interface ServiceStates {
  [key: string]: boolean
}

interface EnvironmentVariables {
  BLUEOS_DISABLE_SERVICES?: string
  [key: string]: string | undefined
}

interface ServiceTooltips {
  [key: string]: string
}

export default Vue.extend({
  name: 'ServiceDisabler',
  data() {
    return {
      states: {} as ServiceStates,
      fetch_service_states_task: new OneMoreTime({ delay: 5000, disposeWith: this }) as OneMoreTime,
      manuallyChanged: {} as Record<string, boolean>,
      services: [
        'autopilot',
        'beacon',
        'bridget',
        'cable_guy',
        'commander',
        'helper',
        'kraken',
        'linux2rest',
        'mavlink2rest',
        'nmea_injector',
        'pardal',
        'ping',
        'ttyd',
        'user_terminal',
        'video',
        'versionchooser',
        'wifi',
        'zenohd',
      ],
      serviceTooltips: {
        autopilot: 'Responsible for managing the autopilot firmware and mavlink communication. '
          + 'Disabling this will stop the autopilot from working.',
        cable_guy: 'Responsible for managing the cable connection to the vehicle. '
          + 'Disabling this may break the connection to the vehicle.',
        video: 'Responsible for managing the video stream from the vehicle. '
          + 'Disabling this will stop the video stream from being displayed.',
        mavlink2rest: 'Responsible for managing the mavlink2rest server. Disablig this '
          + 'will break the frontend communication with the vehicle and some internal services and extensions.',
        kraken: 'Responsible for managing the extensions. Disabling this will break the extensions system.',
        zenohd: 'Responsible for managing the zenoh server.',
        beacon: 'Responsible for managing the mDNS advertisement and some low-priority network services.',
        bridget: 'Responsible for managing serial bridges. Used manually or by the Ping service.',
        commander: 'Responsible for doing operations on the host computer.'
          + 'Used for network management and other operations. '
          + 'Disable this if you are developing on a desktop computer.',
        nmea_injector: 'Responsible for injecting NMEA sentences into the vehicle. Used for GPS and other sensors.',
        wifi: 'Responsible for managing the wifi connections.',
        helper: 'Responsible for service/extensions discovery and network reachability.',
        iperf3: 'Responsible for managing the iperf3 server.',
        linux2rest: 'Used for populating the System Information page, network status, and for serial port detection.',
        filebrowser: 'The file browser on the UI.',
        versionchooser: 'Responsible for managing versions of BlueOS and the UI. '
          + 'Disabling this on a real vehicle WILL make bootstrap reset to factor after a few minutes.',
        pardal: 'Responsible for network speed testing.',
        ping: 'Responsible for detection and management of Ping sonar devices.',
        user_terminal: 'The user terminal on terminal page.',
        ttyd: 'The actual service for the terminal page.',
        nginx: 'The nginx server on the UI.',
        log_zipper: 'Responsible for zipping logs periodically.',
        bag_of_holding: 'Responsible for storing user and extensions settings as a simple json',
      } as ServiceTooltips,
    }
  },
  mounted() {
    this.fetch_service_states_task.setAction(this.refreshStates)
    this.updateStates()
  },

  methods: {
    async refreshStates(): Promise<void> {
      const commander_variables = (await commander.getEnvironmentVariables()) as EnvironmentVariables
      const version_variables = (await getVersionChooserEnvironmentVariables()) as EnvironmentVariables

      const disabled_services = commander_variables?.BLUEOS_DISABLE_SERVICES?.split(',') ?? []
      const version_disabled_services = version_variables?.BLUEOS_DISABLE_SERVICES?.split(',') ?? []
      const all_disabled = new Set([...disabled_services, ...version_disabled_services])

      // Only update states for services that haven't been manually changed
      this.services.forEach((service: string) => {
        if (!this.manuallyChanged[service]) {
          this.$set(this.states, service, !all_disabled.has(service))
        }
      })
    },
    async updateStates(): Promise<void> {
      const commander_variables = (await commander.getEnvironmentVariables()) as EnvironmentVariables
      const version_variables = (await getVersionChooserEnvironmentVariables()) as EnvironmentVariables

      const disabled_services = commander_variables?.BLUEOS_DISABLE_SERVICES?.split(',') ?? []
      const version_disabled_services = version_variables?.BLUEOS_DISABLE_SERVICES?.split(',') ?? []
      const all_disabled = new Set([...disabled_services, ...version_disabled_services])

      // Reset all states based on environment variables
      this.services.forEach((service: string) => {
        this.$set(this.states, service, !all_disabled.has(service))
      })

      // Clear manually changed services
      this.services.forEach((service: string) => {
        this.$set(this.manuallyChanged, service, false)
      })
    },
    async handleServiceStateChange(service: string): Promise<void> {
      const newState = this.states[service]
      try {
        if (!newState) {
          // Service is being disabled - kill it
          await commander.killService(service)
        }

        // Update environment variables for both commander and version chooser
        const commander_variables = (await commander.getEnvironmentVariables()) as EnvironmentVariables
        const version_variables = (await getVersionChooserEnvironmentVariables()) as EnvironmentVariables

        // Get current disabled services
        const disabled_services = new Set(commander_variables?.BLUEOS_DISABLE_SERVICES?.split(',') ?? [])
        const version_disabled_services = new Set(version_variables?.BLUEOS_DISABLE_SERVICES?.split(',') ?? [])

        if (!newState) {
          // Add service to disabled lists
          disabled_services.add(service)
          version_disabled_services.add(service)
        } else {
          // Remove service from disabled lists
          disabled_services.delete(service)
          version_disabled_services.delete(service)

          // Service is being enabled - restart it
          await commander.restartService(service)
        }

        // Update environment variables
        await commander.setEnvironmentVariables({
          BLUEOS_DISABLE_SERVICES: Array.from(disabled_services).join(','),
        })
        await setVersionChooserEnvironmentVariables({
          BLUEOS_DISABLE_SERVICES: Array.from(disabled_services).join(','),
        })

        // Mark this service as manually changed
        this.$set(this.manuallyChanged, service, true)

        notifier.pushSuccess(
          'SERVICE_STATE_UPDATED',
          `Service ${service} ${newState ? 'enabled' : 'disabled'} successfully.`,
        )
      } catch (error) {
        notifier.pushError(
          'SERVICE_STATE_UPDATE_FAILED',
          `Failed to ${newState ? 'enable' : 'disable'} service ${service}: ${error}`,
        )
        // Revert the switch state
        this.$set(this.states, service, !newState)
        // Remove from manually changed since the operation failed
        this.$set(this.manuallyChanged, service, false)
      }
    },
  },
})
</script>

<style scoped>
.service-list {
  max-height: 60vh;
  overflow-y: auto;
}

.service-item {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.service-item:last-child {
  border-bottom: none;
}

.service-item:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

/* Custom scrollbar styling */
.service-list::-webkit-scrollbar {
  width: 8px;
}

.service-list::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
}

.service-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 4px;
}

.service-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.3);
}
</style>
