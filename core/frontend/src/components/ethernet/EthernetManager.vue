<template>
  <v-card
    elevation="1"
    width="400"
  >
    <v-expansion-panels v-if="are_interfaces_available && !updating_interfaces">
      <interface-card
        v-for="(ethernet_interface, key) in available_interfaces"
        :key="key"
        class="available-interface"
        :adapter="ethernet_interface"
        @edit="updateInterface"
      />
    </v-expansion-panels>
    <v-container v-else-if="updating_interfaces">
      <spinning-logo size="30%" />
    </v-container>
    <v-container v-else>
      <div>
        No ethernet interfaces available
      </div>
    </v-container>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import ethernet from '@/store/ethernet'
import notifications from '@/store/notifications'
import { EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

import InterfaceCard from './InterfaceCard.vue'

export default Vue.extend({
  name: 'EthernetManager',
  components: {
    InterfaceCard,
    SpinningLogo,
  },
  computed: {
    are_interfaces_available(): boolean {
      return ethernet.available_interfaces.length > 0
    },
    available_interfaces(): EthernetInterface[] {
      return ethernet.available_interfaces
    },
    updating_interfaces(): boolean {
      return ethernet.updating_interfaces
    },
  },
  methods: {
    async updateInterface(ethernet_interface: EthernetInterface): Promise<void> {
      ethernet.setUpdatingInterfaces(true)
      await back_axios({
        method: 'post',
        url: `${ethernet.API_URL}/ethernet`,
        timeout: 5000,
        data: ethernet_interface,
      })
        .catch((error) => {
          const message = `Could not update ethernet interface: ${error.message}`
          notifications.pushError({ service: ethernet_service, type: 'ETHERNET_INTERFACE_UPDATE_FAIL', message })
        })
    },
  },
})
</script>

<style>
  .available-interface {
      background-color: #f8f8f8;
  }

  .available-interface:hover {
      cursor: pointer;
      background-color: #c5c5c5;
  }
</style>
