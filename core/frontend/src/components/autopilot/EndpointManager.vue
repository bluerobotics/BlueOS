<template>
  <div class="endpoints-manager d-flex flex-column align-center">
    <div
      v-if="are_endpoints_available && !updating_endpoints && !updating_router"
      class="d-flex flex-column align-center justify-center ma-0 pa-0"
      style="width: 80%;"
    >
      <v-divider
        width="80%"
        class="my-4"
      />
      <v-card class="align-center justify-center pa-6 d-block">
        <v-card-title class="ma-0 pa-0 d-block">
          Mavlink Router
        </v-card-title>
        <v-card-text>
          <p>
            Select the router to use for distributing MAVLink data.
          </p>
          <v-radio-group
            v-model="selected_router"
            row
            @change="setCurrentRouter"
          >
            <v-radio v-for="router in available_routers" :key="router" :label="router" :value="router" />
          </v-radio-group>
        </v-card-text>
      </v-card>
      <v-divider
        width="80%"
        class="my-4"
      />
      <template v-for="(endpoint, index) in available_endpoints">
        <v-divider
          v-if="index !== 0"
          :key="index"
          width="80%"
          class="my-4"
        />
        <endpoint-card
          :key="endpoint.name"
          :endpoint="endpoint"
        />
      </template>
    </div>

    <v-container v-else-if="updating_endpoints || updating_router">
      <spinning-logo
        size="30%"
        subtitle="Fetching available endpoints..."
      />
    </v-container>
    <v-card
      v-else
      class="d-flex align-center justify-center pa-6"
    >
      <p class="text-h6">
        No endpoints available.
      </p>
    </v-card>

    <v-fab-transition>
      <v-btn
        :key="'create_button'"
        color="primary"
        fab
        large
        dark
        fixed
        bottom
        right
        class="v-btn--example"
        @click="openCreationDialog"
      >
        <v-icon>mdi-plus</v-icon>
      </v-btn>
    </v-fab-transition>

    <creation-dialog
      v-model="show_creation_dialog"
      @endpointChange="createEndpoint"
    />
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import { OneMoreTime } from '@/one-more-time'
import autopilot from '@/store/autopilot_manager'
import { AutopilotEndpoint } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'
import { fetchAvailableEndpoints } from './AutopilotManagerUpdater'
import EndpointCard from './EndpointCard.vue'
import CreationDialog from './EndpointCreationDialog.vue'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'EndpointManager',
  components: {
    EndpointCard,
    SpinningLogo,
    CreationDialog,
  },
  data() {
    return {
      show_creation_dialog: false,
      selected_router: '',
      available_routers: [] as string[],
      updating_router: false,
      fetch_available_endpoints_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
    }
  },
  computed: {
    updating_endpoints(): boolean {
      return autopilot.updating_endpoints
    },
    available_endpoints(): AutopilotEndpoint[] {
      return autopilot.available_endpoints
    },
    are_endpoints_available(): boolean {
      return !this.available_endpoints.isEmpty()
    },
  },
  mounted() {
    this.fetch_available_endpoints_task.setAction(fetchAvailableEndpoints)
    this.fetchAvailableRouters()
    this.fetchCurrentRouter()
  },
  methods: {
    openCreationDialog(): void {
      this.show_creation_dialog = true
    },
    fetchAvailableRouters(): void {
      back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/available_routers`,
        timeout: 10000,
      })
        .then((response) => {
          this.available_routers = response.data
        })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_ROUTERS_FETCH_FAIL', error, true)
        })
    },
    fetchCurrentRouter(): void {
      back_axios({
        method: 'get',
        url: `${autopilot.API_URL}/preferred_router`,
        timeout: 10000,
      })
        .then((response) => {
          this.selected_router = response.data
        })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_ROUTERS_FETCH_FAIL', error, true)
        })
    },
    async setCurrentRouter(): Promise<void> {
      this.updating_router = true
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/preferred_router`,
        timeout: 10000,
        params: {
          router: this.selected_router,
        },
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_ROUTER_SET_FAIL', error, true)
        })
        .finally(() => {
          this.fetchCurrentRouter()
          this.updating_router = false
        })
    },
    async createEndpoint(endpoint: AutopilotEndpoint): Promise<void> {
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
        data: [endpoint],
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_ENDPOINT_CREATE_FAIL', error, true)
        })
    },
  },
})
</script>

<style scoped>
.endpoints-manager {
  width: 80%;
  margin-bottom: 100px;
}
</style>
