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
      <v-container>
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
        <v-row justify="center">
          <v-btn
            @click.native.stop="openAddressCreationDialog"
          >
            Add new address
          </v-btn>
          <address-creation-dialog
            v-model="show_creation_dialog"
            :interface-name="adapter.name"
          />
        </v-row>
      </v-container>
    </v-expansion-panel-content>
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

export default Vue.extend({
  name: 'InterfaceCard',
  components: {
    AddressCreationDialog,
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
    }
  },
  computed: {
    is_connected(): boolean {
      return this.adapter.info ? this.adapter.info.connected : false
    },
    status_info(): string {
      return this.is_connected ? 'Connected' : 'Not connected'
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
          const message = `Could not delete address '${ip}' on '${this.adapter.name}': ${error.message}.`
          notifications.pushError({ service: ethernet_service, type: 'ETHERNET_ADDRESS_DELETE_FAIL', message })
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
