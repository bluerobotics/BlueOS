<template>
  <v-expansion-panel
    flat
  >
    <v-expansion-panel-header class="interface-header">
      {{ adapter.name }}
      <v-spacer />
      {{ status_info }}
    </v-expansion-panel-header>

    <v-expansion-panel-content>
      <v-container class="px-0">
        <v-row
          v-for="(address, key) in adapter.addresses"
          :key="key"
          height="50"
          align="center"
        >
          <v-col cols="5">
            {{ address.ip }}
          </v-col>
          <v-col cols="5">
            {{ showable_mode_name(address.mode) }}
          </v-col>
          <v-col cols="2">
            <v-btn
              icon
              class="text-center"
              @click.native.stop="deleteAddress(address.ip)"
            >
              <v-icon>
                mdi-delete-circle
              </v-icon>
            </v-btn>
          </v-col>
        </v-row>
        <v-row class="d-flex align-center justify-space-between mx-0 mt-2 pa-0">
          <v-btn
            small
            class="ma-2 px-2 py-5 elevation-1"
            @click.native.stop="openAddressCreationDialog"
          >
            Add <br> static IP
          </v-btn>
          <address-creation-dialog
            v-model="show_creation_dialog"
            :interface-name="adapter.name"
          />
          <v-btn
            small
            class="ma-2 px-2 py-5 elevation-1"
            @click="triggerForDynamicIP"
          >
            Ask for <br> dynamic IP
          </v-btn>
          <v-btn
            v-if="is_there_dhcp_server_already"
            small
            class="ma-2 px-2 py-5 elevation-1"
            @click="removeDHCPServer"
          >
            Disable <br> DHCP server
          </v-btn>
          <v-btn
            v-else
            small
            class="ma-2 px-2 py-5 elevation-1"
            :disabled="!is_static_ip_present"
            @click="openDHCPServerDialog"
          >
            Enable <br> DHCP server
          </v-btn>
        </v-row>
      </v-container>
    </v-expansion-panel-content>
    <dhcp-server-dialog
      v-model="show_dhcp_server_dialog"
      :adapter="adapter"
    />
  </v-expansion-panel>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import ethernet from '@/store/ethernet'
import notifications from '@/store/notifications'
import { AddressMode, EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

import AddressCreationDialog from './AddressCreationDialog.vue'
import DHCPServerDialog from './DHCPServerDialog.vue'

export default Vue.extend({
  name: 'InterfaceCard',
  components: {
    AddressCreationDialog,
    'dhcp-server-dialog': DHCPServerDialog,
  },
  props: {
    adapter: {
      type: Object as PropType<EthernetInterface>,
      required: true,
    },
  },

  data() {
    return {
      show_creation_dialog: false,
      show_dhcp_server_dialog: false,
    }
  },
  computed: {
    is_connected(): boolean {
      return this.adapter.info ? this.adapter.info.connected : false
    },
    status_info(): string {
      return this.is_connected ? 'Connected' : 'Not connected'
    },
    is_there_dhcp_server_already(): boolean {
      return this.adapter.addresses.some((address) => address.mode === AddressMode.server)
    },
    is_static_ip_present(): boolean {
      return this.adapter.addresses.some((address) => address.mode === AddressMode.unmanaged)
    },
  },
  methods: {
    showable_mode_name(mode: AddressMode): string {
      switch (mode) {
        case AddressMode.client: return 'Dynamic IP'
        case AddressMode.server: return 'DHCP Server'
        case AddressMode.unmanaged: return 'Static IP'
        default: return 'Undefined mode'
      }
    },
    openAddressCreationDialog(): void {
      this.show_creation_dialog = true
    },
    async deleteAddress(ip: string): Promise<void> {
      ethernet.setUpdatingInterfaces(true)

      await back_axios({
        method: 'delete',
        url: `${ethernet.API_URL}/address`,
        timeout: 10000,
        params: { interface_name: this.adapter.name, ip_address: ip },
      })
        .catch((error) => {
          const message = error.response?.data?.detail ?? error.message
          notifications.pushError({ service: ethernet_service, type: 'ETHERNET_ADDRESS_DELETE_FAIL', message })
        })
    },
    async triggerForDynamicIP(): Promise<void> {
      ethernet.setUpdatingInterfaces(true)

      await back_axios({
        method: 'post',
        url: `${ethernet.API_URL}/dynamic_ip`,
        timeout: 10000,
        params: { interface_name: this.adapter.name },
      })
        .catch((error) => {
          const message = `Could not trigger for dynamic IP address on '${this.adapter.name}': ${error.message}.`
          notifications.pushError({ service: ethernet_service, type: 'DYNAMIC_IP_TRIGGER_FAIL', message })
        })
    },
    openDHCPServerDialog(): void {
      this.show_dhcp_server_dialog = true
    },
    async removeDHCPServer(): Promise<void> {
      ethernet.setUpdatingInterfaces(true)

      await back_axios({
        method: 'delete',
        url: `${ethernet.API_URL}/dhcp`,
        timeout: 10000,
        params: { interface_name: this.adapter.name },
      })
        .catch((error) => {
          const message = `Could not remove DHCP server from interface '${this.adapter.name}': ${error.message}.`
          notifications.pushError({ service: ethernet_service, type: 'DHCP_SERVER_REMOVE_FAIL', message })
        })
    },
  },
})
</script>

<style>
.interface-header {
  background-color: #2799D2
}
</style>
