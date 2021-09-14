<template>
  <v-card
    width="500"
    elevation="0"
    class="mb-12 pb-12 endpoints-list"
  >
    <v-list
      v-if="available_endpoints && !updating_endpoints"
      dense
    >
      <template v-for="(endpoint, index) in available_endpoints">
        <v-divider
          v-if="index!==0"
          :key="index"
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
      <spinning-logo />
    </v-container>
    <v-container v-else>
      <div>
        No endpoints available
      </div>
    </v-container>

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
    />

    <autopilot-manager-updater />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import AutopilotManagerStore from '@/store/autopilot_manager'
import { AutopilotEndpoint } from '@/types/autopilot'

import SpinningLogo from '../common/SpinningLogo.vue'
import AutopilotManagerUpdater from './AutopilotManagerUpdater.vue'
import EndpointCard from './EndpointCard.vue'
import CreationDialog from './EndpointCreationDialog.vue'

const autopilot_manager_store: AutopilotManagerStore = getModule(AutopilotManagerStore)

export default Vue.extend({
  name: 'WifiManager',
  components: {
    EndpointCard,
    SpinningLogo,
    CreationDialog,
    AutopilotManagerUpdater,
  },
  data() {
    return {
      show_creation_dialog: false,
    }
  },
  computed: {
    updating_endpoints(): boolean {
      return autopilot_manager_store.updating_endpoints
    },
    available_endpoints(): AutopilotEndpoint[] {
      return autopilot_manager_store.available_endpoints
    },
  },
  methods: {
    openCreationDialog(): void {
      this.show_creation_dialog = true
    },
  },
})
</script>

<style scoped>
.endpoints-list {
    max-width: 70%;
    margin: auto;
}
</style>
