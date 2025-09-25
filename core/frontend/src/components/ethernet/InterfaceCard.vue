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
          <span
            v-else
            v-tooltip="!is_static_ip_present ? 'A static IP address is required to enable DHCP server.' : undefined"
          >
            <v-btn
              small
              class="ma-2 px-2 py-5 elevation-1"
              :disabled="!is_static_ip_present"
              @click="openDHCPServerDialog"
            >
              Enable <br> DHCP server
            </v-btn>
          </span>
        </v-row>

        <!-- DHCP Leases Section -->
        <v-row v-if="is_there_dhcp_server_already" class="mt-4">
          <v-col cols="12">
            <v-card flat>
              <v-card-title
                class="text-h6 py-2 cursor-pointer"
                @click="toggleLeasesExpanded"
              >
                <v-icon
                  :class="{ 'rotate-180': leases_expanded }"
                  class="transition-transform mr-2"
                >
                  mdi-chevron-down
                </v-icon>
                DHCP Leases
                <v-spacer />
                <v-btn
                  small
                  icon
                  :loading="loading_leases"
                  @click.stop="refreshLeases"
                >
                  <v-icon>mdi-refresh</v-icon>
                </v-btn>
              </v-card-title>
              <v-expand-transition>
                <v-card-text v-show="leases_expanded" class="pt-0">
                  <div style="max-height: 300px; overflow-y: auto;">
                    <v-data-table
                      :headers="lease_headers"
                      :items="dhcp_leases"
                      :loading="loading_leases"
                      dense
                      hide-default-footer
                      class="elevation-0"
                    >
                      <template #item.ip="{ item }">
                        <span class="font-weight-medium">{{ item.ip }}</span>
                      </template>
                      <template #item.mac="{ item }">
                        <span class="font-family-monospace">{{ item.mac }}</span>
                      </template>
                      <template #item.hostname="{ item }">
                        <span v-if="item.hostname">{{ item.hostname }}</span>
                        <span v-else class="text--secondary">-</span>
                      </template>
                      <template #item.expires_at="{ item }">
                        <span :class="getLeaseExpiryClass(item)">
                          {{ formatLeaseExpiry(item.expires_at) }}
                        </span>
                      </template>
                      <template #item.is_active="{ item }">
                        <v-chip
                          :color="item.is_active ? 'success' : 'error'"
                          small
                          text-color="white"
                        >
                          {{ item.is_active ? 'Active' : 'Expired' }}
                        </v-chip>
                      </template>
                    </v-data-table>
                  </div>
                  <div v-if="dhcp_leases.length === 0 && !loading_leases" class="text-center py-4 text--secondary">
                    No DHCP leases found
                  </div>
                </v-card-text>
              </v-expand-transition>
            </v-card>
          </v-col>
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
import { AddressMode, DHCPServerLease, EthernetInterface } from '@/types/ethernet'
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
      dhcp_leases: [] as DHCPServerLease[],
      loading_leases: false,
      leases_expanded: false,
      lease_headers: [
        { text: 'IP Address', value: 'ip', sortable: false },
        { text: 'MAC Address', value: 'mac', sortable: false },
        { text: 'Hostname', value: 'hostname', sortable: false },
        { text: 'Expires', value: 'expires_at', sortable: false },
        { text: 'Status', value: 'is_active', sortable: false },
      ],
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
      return this.adapter.addresses.some(
        (address) => [AddressMode.server, AddressMode.backupServer].includes(address.mode),
      )
    },
    is_static_ip_present(): boolean {
      return this.adapter.addresses.some((address) => address.mode === AddressMode.unmanaged)
    },
    is_interface_last_ip_address(): boolean {
      return this.adapter.addresses.length === 1
    },
  },
  watch: {
    'adapter.name': {
      handler() {
        this.fetchLeases()
      },
      immediate: true,
    },
    is_there_dhcp_server_already: {
      handler() {
        this.fetchLeases()
      },
      immediate: true,
    },
  },
  mounted() {
    beacon.registerBeaconListener(this)
    this.fetchLeases()
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
        case AddressMode.backupServer: return 'Backup DHCP Server'
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
    async fetchLeases(): Promise<void> {
      if (!this.is_there_dhcp_server_already) {
        this.dhcp_leases = []
        return
      }

      this.loading_leases = true
      try {
        const response = await back_axios({
          method: 'get',
          url: `${ethernet.API_URL}/dhcp/leases`,
          timeout: 10000,
        })

        // Get leases for this specific interface
        const interfaceLeases = response.data[this.adapter.name] ?? []
        this.dhcp_leases = interfaceLeases.map((lease: DHCPServerLease) => ({
          ...lease,
          expires_at: new Date(lease.expires_at),
          is_active: lease.expires_epoch > Date.now() / 1000,
        }))
      } catch (error) {
        console.error('Failed to fetch DHCP leases:', error)
        this.dhcp_leases = []
      } finally {
        this.loading_leases = false
      }
    },
    async refreshLeases(): Promise<void> {
      await this.fetchLeases()
    },
    toggleLeasesExpanded(): void {
      this.leases_expanded = !this.leases_expanded
    },
    formatLeaseExpiry(expiresAt: Date): string {
      const now = new Date()
      const diffMs = expiresAt.getTime() - now.getTime()
      const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
      const diffMinutes = Math.floor(diffMs % (1000 * 60 * 60) / (1000 * 60))

      if (diffMs < 0) {
        return 'Expired'
      }
      if (diffHours > 0) {
        return `${diffHours}h ${diffMinutes}m`
      }
      return `${diffMinutes}m`
    },
    getLeaseExpiryClass(lease: DHCPServerLease): string {
      const now = new Date()
      const diffMs = lease.expires_at.getTime() - now.getTime()
      const diffHours = diffMs / (1000 * 60 * 60)

      if (diffMs < 0) {
        return 'error--text'
      }
      if (diffHours < 1) {
        return 'warning--text'
      }
      return 'success--text'
    },
  },
})
</script>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}

.rotate-180 {
  transform: rotate(180deg);
}

.transition-transform {
  transition: transform 0.2s ease;
}
</style>
