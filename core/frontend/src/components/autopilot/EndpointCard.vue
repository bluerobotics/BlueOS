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
                class="ma-1"
                :disabled="!endpoint.persistent"
              >
                mdi-content-save
              </v-icon>
              <v-icon
                class="ma-1"
                :disabled="!endpoint.protected"
              >
                mdi-lock
              </v-icon>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
      <v-fab-transition>
        <v-btn
          color="pink"
          fab
          dark
          small
          absolute
          bottom
          right
          :disabled="endpoint.protected"
          @click="removeEndpoint"
        >
          <v-icon>mdi-minus</v-icon>
        </v-btn>
      </v-fab-transition>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import axios from 'axios'
import Vue, { PropType } from 'vue'
import { getModule } from 'vuex-module-decorators'

import AutopilotManagerStore from '@/store/autopilot_manager'
import NotificationStore from '@/store/notifications'
import { AutopilotEndpoint, userFriendlyEndpointType } from '@/types/autopilot'
import { autopilot_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

const notification_store: NotificationStore = getModule(NotificationStore)
const autopilot_manager_store: AutopilotManagerStore = getModule(AutopilotManagerStore)

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
    }
  },
  methods: {
    async removeEndpoint(): Promise<void> {
      autopilot_manager_store.setUpdatingEndpoints(true)
      await axios({
        method: 'delete',
        url: `${autopilot_manager_store.API_URL}/endpoints`,
        timeout: 10000,
        data: [this.endpoint],
      })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_manager_service,
            'AUTOPILOT_ENDPOINT_DELETE_FAIL',
            `Could not remove endpoint: ${error.message}.`,
          ))
        })
    },
  },
})
</script>
