<template>
  <v-card
    width="500"
    elevation="0"
    class="mb-12 pa-6 endpoints-list"
  >
    <v-list
      v-if="are_endpoints_available && !updating_endpoints"
      style="background-color: transparent"
      dense
    >
      <template v-for="(endpoint, index) in available_endpoints">
        <v-divider
          v-if="index!==0"
          :key="`spacer-${index}`"
        />
        <v-list-item
          :key="index"
          class="pa-0"
        >
          <endpoint-card :endpoint="endpoint" />
        </v-list-item>
      </template>
    </v-list>

    <v-container v-else-if="updating_endpoints">
      <spinning-logo size="30%" />
    </v-container>
    <v-card
      v-else
      class="d-flex align-center justify-center ma-12"
      height="100"
      elevation="1"
    >
      <p class="text-h6">
        No endpoints available.
      </p>
    </v-card>

    <v-fab-transition>
      <v-btn
        :key="'create_button'"
        :color="'blue'"
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
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import { AutopilotEndpoint } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'
import EndpointCard from './EndpointCard.vue'
import CreationDialog from './EndpointCreationDialog.vue'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'WifiManager',
  components: {
    EndpointCard,
    SpinningLogo,
    CreationDialog,
  },
  data() {
    return {
      show_creation_dialog: false,
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
      return this.available_endpoints.length !== 0
    },
  },
  methods: {
    openCreationDialog(): void {
      this.show_creation_dialog = true
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
.endpoints-list {
    max-width: 70%;
    margin: auto;
    background-color: transparent;
}
</style>
