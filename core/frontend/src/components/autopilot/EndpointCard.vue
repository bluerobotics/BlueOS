<template>
  <v-card
    width="100%"
    class="available-endpoint pa-0 my-4"
  >
    <v-card-text class="pa-2">
      <v-container class="pa-1">
        <v-row>
          <v-col
            cols="6"
            class="pa-1"
          >
            <v-card class="elevation-0 d-flex flex-column align-center pa-0">
              <p class="ma-0 pt-2 text-h5">
                {{ endpoint.name }}
              </p>
              <p class="ma-0 pb-2 text-body-2">
                {{ endpoint.owner }}
              </p>
            </v-card>
          </v-col>
          <v-col
            cols="4"
            class="pa-1"
          >
            <v-card class="elevation-0 d-flex flex-column align-center pa-0">
              <v-simple-table
                dense
                class="text-center"
              >
                <template #default>
                  <tbody>
                    <tr>
                      <td>{{ userFriendlyEndpointType(endpoint.connection_type) }}</td>
                    </tr>
                    <tr>
                      <td>{{ endpoint.place }}</td>
                    </tr>
                    <tr>
                      <td>{{ endpoint.argument }}</td>
                    </tr>
                  </tbody>
                </template>
              </v-simple-table>
            </v-card>
          </v-col>
          <v-col
            cols="2"
            class="pa-1"
          >
            <v-card class="elevation-0 d-flex flex-column align-center pa-0">
              <v-icon
                v-tooltip="persistency.tooltip"
                class="ma-1"
              >
                {{ persistency.icon }}
              </v-icon>
              <v-icon
                v-tooltip="protection.tooltip"
                class="ma-1"
              >
                {{ protection.icon }}
              </v-icon>
              <v-icon
                v-tooltip="status.tooltip"
                class="ma-1"
              >
                {{ status.icon }}
              </v-icon>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-card-text>
    <v-speed-dial
      v-if="!endpoint.protected"
      v-model="floating_action_button"
      class="endpoint-edit-fab"
      right
      direction="left"
      transition="slide-y-reverse-transition"
      absolute
    >
      <template #activator>
        <v-btn
          v-model="floating_action_button"
          color="pink"
          dark
          fab
          small
          relative
        >
          <v-icon v-if="floating_action_button">
            mdi-close
          </v-icon>
          <v-icon v-else>
            mdi-pencil
          </v-icon>
        </v-btn>
      </template>
      <v-btn
        color="pink"
        fab
        dark
        small
        relative
        @click="toggleEndpointEnabled"
      >
        <v-icon
          v-if="endpoint.enabled"
          v-tooltip="disable_action.tooltip"
        >
          {{ disable_action.icon }}
        </v-icon>
        <v-icon
          v-else
          v-tooltip="enable_action.tooltip"
        >
          {{ enable_action.icon }}
        </v-icon>
      </v-btn>
      <v-btn
        v-tooltip="remove_action.tooltip"
        color="red"
        fab
        dark
        small
        relative
        :disabled="endpoint.protected"
        @click="removeEndpoint"
      >
        <v-icon>{{ remove_action.icon }}</v-icon>
      </v-btn>
    </v-speed-dial>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { AutopilotEndpoint, userFriendlyEndpointType } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

export default Vue.extend({
  name: 'EndpointCard',
  props: {
    endpoint: {
      type: Object as PropType<AutopilotEndpoint>,
      required: true,
    },
  },
  data() {
    return {
      userFriendlyEndpointType,
      floating_action_button: false,
      updated_endpoint: this.endpoint,
    }
  },
  computed: {
    persistency(): { icon: string, tooltip: string } {
      if (this.endpoint.persistent) {
        return { icon: 'mdi-content-save', tooltip: 'Persistent' }
      }
      return { icon: 'mdi-content-save-off', tooltip: 'Not persistent' }
    },
    protection(): { icon: string, tooltip: string } {
      if (this.endpoint.protected) {
        return { icon: 'mdi-lock', tooltip: 'Protected' }
      }
      return { icon: 'mdi-lock-off', tooltip: 'Not protected' }
    },
    status(): { icon: string, tooltip: string } {
      if (this.endpoint.enabled) {
        return { icon: 'mdi-lightbulb-on', tooltip: 'Enabled' }
      }
      return { icon: 'mdi-lightbulb-off', tooltip: 'Disabled' }
    },
    enable_action(): { icon: string, tooltip: string } {
      return { icon: 'mdi-lightbulb-on', tooltip: 'Enable' }
    },
    disable_action(): { icon: string, tooltip: string } {
      return { icon: 'mdi-lightbulb-off', tooltip: 'Disable' }
    },
    remove_action(): { icon: string, tooltip: string } {
      return { icon: 'mdi-delete', tooltip: 'Remove' }
    },
  },
  methods: {
    async removeEndpoint(): Promise<void> {
      autopilot.setUpdatingEndpoints(true)
      await back_axios({
        method: 'delete',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
        data: [this.endpoint],
      })
        .catch((error) => {
          const message = error.response.data.detail ?? error.message
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_ENDPOINT_DELETE_FAIL', message })
        })
    },
    async toggleEndpointEnabled(): Promise<void> {
      this.updated_endpoint.enabled = !this.updated_endpoint.enabled
      this.updateEndpoint()
    },
    async updateEndpoint(): Promise<void> {
      autopilot.setUpdatingEndpoints(true)
      await back_axios({
        method: 'put',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
        data: [this.updated_endpoint],
      })
        .catch((error) => {
          const message = error.response.data.detail ?? error.message
          notifications.pushError({ service: autopilot_service, type: 'AUTOPILOT_ENDPOINT_UPDATE_FAIL', message })
        })
    },
  },
})
</script>

<style scoped>
.endpoint-edit-fab {
  bottom: 32%;
  left: 96%;
}
</style>
