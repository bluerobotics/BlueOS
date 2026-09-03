<template>
  <v-card
    class="endpoint-card d-flex justify-space-between align-center justify-center"
  >
    <div class="endpoint-name align-center justify-center">
      <p class="text-h6 text-center ma-0">
        {{ endpoint.name }}
      </p>
      <p class="text-body-2 text-center ma-0">
        {{ endpoint.owner }}
      </p>
    </div>
    <div
      min-width="106px"
      class="endpoint-details d-flex flex-column justify-center elevation-0 pa-1"
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
      class="endpoint-flags d-flex justify-center elevation-0 pa-1"
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
        v-tooltip="enable_tooltip"
        color="primary"
        class="my-1 ml-2"
        hide-details
        dense
        :disabled="!is_known_type"
        @change="toggleEndpointEnabled"
      />
    </div>
    <div class="endpoint-buttons">
      <v-btn
        v-if="!endpoint.protected && is_known_type"
        v-tooltip="'Edit endpoint'"
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
        v-tooltip="`Copy command line string (${command_line_string})`"
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
        v-if="!endpoint.protected || !is_known_type"
        v-tooltip="'Delete endpoint'"
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
import { AutopilotEndpoint, isKnownEndpointType, userFriendlyEndpointType } from '@/types/autopilot'
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
    is_known_type(): boolean {
      return isKnownEndpointType(this.endpoint.connection_type)
    },
    enable_tooltip(): string {
      if (!this.is_known_type) {
        return 'This endpoint type is not supported'
      }
      return this.updated_endpoint.enabled ? 'Disable endpoint' : 'Enable endpoint'
    },
    command_line_string(): string {
      return `${this.endpoint.connection_type}:${window.location.host}:${this.endpoint.argument}`
    },
  },
  methods: {
    async copyEndpoint(): Promise<void> {
      await copyToClipboard(this.command_line_string)
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
.endpoint-card {
  width: 80%;
  height: 130px;
}

.endpoint-name {
  width: 20%;
  margin-left: 20px;
}

.endpoint-flags {
  flex-direction: column;
  margin-right: 20px;
}

.endpoint-buttons {
  gap: 8px;
  display: flex;
  position: absolute;
  right: -16px;
  top: 50%;
  transform: translateY(-50%);
  flex-direction: column;
}

@media (max-width: 600px) {
  .endpoint-card {
    width: 100%;
    height: auto;
    flex-wrap: wrap;
    row-gap: 8px;
    padding: 12px 0;
  }

  .endpoint-details,
  .endpoint-flags {
    flex: 1 1 50%;
    justify-content: center;
    min-width: 0;
  }

  .endpoint-name,
  .endpoint-buttons {
    flex: 1 1 100%;
    justify-content: center;
  }

  .endpoint-name {
    width: auto;
    margin-left: 0;
  }

  .endpoint-flags {
    flex-direction: row;
    align-items: center;
    margin-right: 0;
  }

  .endpoint-buttons {
    position: static;
    flex-direction: row;
    transform: none;
  }
}
</style>
