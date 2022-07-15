<template>
  <v-card
    width="100%"
    class="available-bridge pa-0 my-4"
  >
    <v-card-text class="pa-4">
      <v-tooltip
        top
        :disabled="!(bridge_serial_info.serial_info && bridge_serial_info.serial_info.by_path)"
      >
        <template #activator="{ on, attrs }">
          <v-container
            class="pa-0"
            v-bind="attrs"
            v-on="on"
          >
            <v-card class="elevation-0 pa-0">
              <v-card-text
                class="d-flex align-center pa-0 justify-center"
              >
                <span class="text-subtitle-1 mr-2">
                  {{ get_display_name(bridge_serial_info) }}:{{ bridge_serial_info.bridge.baud }}
                </span>
                <v-icon>mdi-link</v-icon>
                <span class="text-subtitle-1 ml-2">
                  {{ bridge_serial_info.bridge.ip }}:{{ bridge_serial_info.bridge.udp_port }}
                </span>
              </v-card-text>
            </v-card>
          </v-container>
        </template>
        <span v-if="bridge_serial_info.serial_info">
          <div class="d-flex flex-column">
            <p class="subtitle-1 text-center ma-0">
              Path: {{ bridge_serial_info.serial_info.by_path }}
            </p>
            <p class="subtitle-1 text-center ma-0">
              Info:
              {{ bridge_serial_info.serial_info.udev_properties["ID_VENDOR"] }}
              /
              {{ bridge_serial_info.serial_info.udev_properties["ID_MODEL"] }}
            </p>
          </div></span>
      </v-tooltip>
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
import { BridgeWithSerialInfo } from '@/types/bridges'
import { bridget_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(bridget_service)

export default Vue.extend({
  name: 'BridgeCard',
  props: {
    bridge_serial_info: {
      type: Object as PropType<BridgeWithSerialInfo>,
      required: true,
    },
  },
  methods: {
    get_display_name(bridge_serial_info: BridgeWithSerialInfo): string {
      return bridge_serial_info.serial_info?.name ?? bridge_serial_info.bridge.serial_path
    },
    async removeBridge(): Promise<void> {
      bridget.setUpdatingBridges(true)
      await back_axios({
        method: 'delete',
        url: `${bridget.API_URL}/bridges`,
        timeout: 10000,
        data: this.bridge_serial_info.bridge,
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
