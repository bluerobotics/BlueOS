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
      <spinning-logo />
    </v-container>
    <v-container v-else>
      <div>
        No ethernet interfaces available
      </div>
    </v-container>
    <ethernet-updater />
  </v-card>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'
import { getModule } from 'vuex-module-decorators'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import EthernetStore from '@/store/ethernet'
import NotificationsStore from '@/store/notifications'
import { EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'

import EthernetUpdater from './EthernetUpdater.vue'
import InterfaceCard from './InterfaceCard.vue'

const notification_store: NotificationsStore = getModule(NotificationsStore)
const ethernet_store: EthernetStore = getModule(EthernetStore)

export default Vue.extend({
  name: 'EthernetManager',
  components: {
    InterfaceCard,
    EthernetUpdater,
    SpinningLogo,
  },
  computed: {
    are_interfaces_available(): boolean {
      return ethernet_store.available_interfaces.length > 0
    },
    available_interfaces(): EthernetInterface[] {
      return ethernet_store.available_interfaces
    },
    updating_interfaces(): boolean {
      return ethernet_store.updating_interfaces
    },
  },
  methods: {
    async updateInterface(ethernet_interface: EthernetInterface): Promise<void> {
      ethernet_store.setUpdatingInterfaces(true)
      await axios({
        method: 'post',
        url: `${ethernet_store.API_URL}/ethernet`,
        timeout: 5000,
        data: ethernet_interface,
      })
        .catch((error) => {
          notification_store.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            ethernet_service,
            'ETHERNET_INTERFACE_UPDATE_FAIL',
            `Could not update ethernet interface: ${error.message}`,
          ))
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
