<template>
  <v-card
    width="80%"
    height="130px"
    class="d-flex justify-space-between align-center justify-center"
  >
    <div
      class="align-center justify-center ml-5"
      style="width: 20%;"
    >
      <p class="text-h6 text-center ma-0">
        {{ endpoint.name }}
      </p>
      <p class="text-body-2 text-center ma-0">
        {{ endpoint.owner }}
      </p>
    </div>
    <div
      min-width="106px"
      class="d-flex flex-column justify-center elevation-0 pa-1"
    >
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
    </div>
    <div
      width="62px"
      class="d-flex flex-column justify-center elevation-0 pa-1 mr-5"
    >
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
      <v-switch
        v-model="updated_endpoint.enabled"
        v-tooltip="updated_endpoint.enabled ? 'Disable endpoint' : 'Enable endpoint'"
        color="primary"
        class="my-1 ml-2"
        hide-details
        dense
        @change="toggleEndpointEnabled"
      />
    </div>
    <div class="endpoint-buttons">
      <v-btn
        v-if="!endpoint.protected"
        color="primary"
        dark
        fab
        x-small
        @click="openEditDialog"
      >
        <v-icon>
          mdi-pencil
        </v-icon>
      </v-btn>
      <v-btn
        color="primary"
        dark
        fab
        x-small
        @click="copyEndpoint"
      >
        <v-icon>
          mdi-content-copy
        </v-icon>
      </v-btn>
      <v-btn
        v-if="!endpoint.protected"
        color="error"
        dark
        fab
        x-small
        @click="removeEndpoint"
      >
        <v-icon>
          mdi-trash-can
        </v-icon>
      </v-btn>
    </div>

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

import { copyToClipboard } from '@/cosmos'
import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import { AutopilotEndpoint, userFriendlyEndpointType } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'
import { sleep } from '@/utils/helper_functions'

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
      updated_endpoint: { ...this.endpoint },
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
  },
  methods: {
    async copyEndpoint(): Promise<void> {
      await copyToClipboard(`${this.endpoint.connection_type}:${window.location.host}:${this.endpoint.argument}`)
    },
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
      // Sleep for half a second so user can see the switch-toggling animation
      await sleep(500)
      this.updateEndpoint(this.updated_endpoint)
    },
    openEditDialog(): void {
      this.updated_endpoint = { ...this.endpoint }
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
.endpoint-buttons {
  gap: 8px;
  position: absolute;
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  flex-direction: column;
}
</style>
