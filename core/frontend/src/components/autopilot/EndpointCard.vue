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
              <p class="ma-0 pt-2 text-h5 text-center">
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
                @click="toggleEndpointEnabled"
              >
                {{ status.icon }}
              </v-icon>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-card-text>
    <v-btn
      v-if="!endpoint.protected"
      color="blue"
      class="endpoint-edit-btn"
      dark
      fab
      x-small
      absolute
      right
      @click="openEditDialog"
    >
      <v-icon>
        mdi-pencil
      </v-icon>
    </v-btn>
    <v-btn
      v-if="!endpoint.protected"
      color="pink"
      class="endpoint-remove-btn"
      dark
      fab
      x-small
      absolute
      right
      @click="removeEndpoint"
    >
      <v-icon>
        mdi-trash-can
      </v-icon>
    </v-btn>

    <endpoint-creation-dialog
      v-model="show_edit_dialog"
      :base-endpoint="updated_endpoint"
      edit
      @endpointChange="updateEndpoint"
    />
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import { AutopilotEndpoint, userFriendlyEndpointType } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

import EndpointCreationDialog from './EndpointCreationDialog.vue'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'EndpointCard',
  components: {
    EndpointCreationDialog,
  },
  props: {
    endpoint: {
      type: Object as PropType<AutopilotEndpoint>,
      required: true,
    },
  },
  data() {
    return {
      userFriendlyEndpointType,
      show_edit_dialog: false,
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
        return { icon: 'mdi-lightbulb-on', tooltip: 'Disable endpoint' }
      }
      return { icon: 'mdi-lightbulb-off', tooltip: 'Enable endpoint' }
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
          notifier.pushBackError('AUTOPILOT_ENDPOINT_DELETE_FAIL', error, true)
        })
    },
    async toggleEndpointEnabled(): Promise<void> {
      this.updated_endpoint.enabled = !this.updated_endpoint.enabled
      this.updateEndpoint(this.updated_endpoint)
    },
    openEditDialog(): void {
      this.show_edit_dialog = true
    },
    async updateEndpoint(endpoint: AutopilotEndpoint): Promise<void> {
      autopilot.setUpdatingEndpoints(true)
      await back_axios({
        method: 'put',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
        data: [endpoint],
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_ENDPOINT_UPDATE_FAIL', error, true)
        })
    },
  },
})
</script>

<style scoped>
.endpoint-edit-btn {
  bottom: 55%;
  left: 97%;
}
.endpoint-remove-btn {
  bottom: 15%;
  left: 97%;
}
</style>
