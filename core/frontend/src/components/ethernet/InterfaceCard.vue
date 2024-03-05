<template>
  <v-expansion-panel
    flat
  >
    <v-expansion-panel-header color="primary">
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
              class="text-center elevation-1"
              color="error"
              icon
              @click.native.stop="deleteAddress(address.ip)"
            >
              <v-icon>
                mdi-delete
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
          <address-deletion-dialog
            ref="deletionDialog"
            v-model="show_deletion_dialog"
            :dialog-type="deletion_dialog_type"
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

import Notifier from '@/libs/notifier'
import beacon from '@/store/beacon'
import ethernet from '@/store/ethernet'
import { AddressMode, EthernetInterface } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

import AddressCreationDialog from './AddressCreationDialog.vue'
import AddressDeletionDialog from './AddressDeletionDialog.vue'
import DHCPServerDialog from './DHCPServerDialog.vue'

const notifier = new Notifier(ethernet_service)

export default Vue.extend({
  name: 'InterfaceCard',
  components: {
    AddressCreationDialog,
    AddressDeletionDialog,
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
      show_deletion_dialog: false,
      show_dhcp_server_dialog: false,
      deletion_dialog_type: '',
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
    is_interface_last_ip_address(): boolean {
      return this.adapter.addresses.length === 1
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
  },
  methods: {
    async fireConfirmDeletionModal(type: 'last-ip-address' | 'ip-being-used'): Promise<boolean> {
      const dialog = this.$refs.deletionDialog as InstanceType<typeof AddressDeletionDialog>

      this.deletion_dialog_type = type
      this.show_deletion_dialog = true

      return new Promise((resolve) => {
        dialog.resolveCallback = resolve
      })
    },
    /**
     * Opens a dialog and requests the user to confirm the deletion of the IP address.
     * @returns {Promise<boolean>} - Resolves to true if no confirmation is needed or
     * granted and false otherwise.
     */
    async confirm_last_interface_ip(): Promise<boolean> {
      if (this.is_interface_last_ip_address) {
        return this.fireConfirmDeletionModal('last-ip-address')
      }

      return true
    },
    /**
     * Opens a dialog and requests the user to confirm the deletion of current used IP address.
     * @returns {Promise<boolean>} - Resolves to true if no confirmation is needed or
     * granted and false otherwise.
     */
    async confirm_ip_being_used(ip: string): Promise<boolean> {
      const ip_being_used = ip === beacon.nginx_ip_address

      if (ip_being_used) {
        return this.fireConfirmDeletionModal('ip-being-used')
      }

      return true
    },
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
      const confirmed_ip_used = await this.confirm_ip_being_used(ip)
      const confirmed_last_ip = confirmed_ip_used && await this.confirm_last_interface_ip()

      if (!confirmed_ip_used || !confirmed_last_ip) {
        return
      }

      ethernet.setUpdatingInterfaces(true)

      await back_axios({
        method: 'delete',
        url: `${ethernet.API_URL}/address`,
        timeout: 10000,
        params: { interface_name: this.adapter.name, ip_address: ip },
      })
        .catch((error) => {
          notifier.pushBackError('ETHERNET_ADDRESS_DELETE_FAIL', error)
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
          notifier.pushError('DYNAMIC_IP_TRIGGER_FAIL', message)
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
          notifier.pushError('DHCP_SERVER_REMOVE_FAIL', message)
        })
    },
  },
})
</script>
