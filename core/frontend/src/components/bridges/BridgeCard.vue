<template>
  <v-card
    width="100%"
    class="available-bridge pa-0 my-4"
  >
    <v-card-text class="pa-4">
      <v-container class="pa-0">
        <v-card class="elevation-0 pa-0">
          <v-card-text
            class="d-flex align-center pa-0 justify-center"
          >
            <span class="text-subtitle-1 mr-2">
              {{ bridge.serial_path }}:{{ bridge.baud }}
            </span>
            <v-icon>mdi-link</v-icon>
            <span class="text-subtitle-1 ml-2">
              {{ bridge.ip }}:{{ bridge.udp_port }}
            </span>
          </v-card-text>
        </v-card>
      </v-container>
      <v-fab-transition>
        <v-btn
          color="error"
          class="bridge-remove-btn"
          fab
          dark
          small
          absolute
          @click="removeBridge"
        >
          <v-icon>mdi-minus</v-icon>
        </v-btn>
      </v-fab-transition>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import Notifier from '@/libs/notifier'
import bridget from '@/store/bridget'
import { Bridge } from '@/types/bridges'
import { bridget_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(bridget_service)

export default Vue.extend({
  name: 'BridgeCard',
  props: {
    bridge: {
      type: Object as PropType<Bridge>,
      required: true,
    },
  },
  methods: {
    async removeBridge(): Promise<void> {
      bridget.setUpdatingBridges(true)
      await back_axios({
        method: 'delete',
        url: `${bridget.API_URL}/bridges`,
        timeout: 10000,
        data: this.bridge,
      })
        .catch((error) => {
          notifier.pushBackError('BRIDGE_DELETE_FAIL', error)
        })
    },
  },
})
</script>

<style scoped>
.bridge-remove-btn {
  bottom: 15%;
  left: 95%;
}
</style>
