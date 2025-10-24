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

        <v-row v-if="is_there_dhcp_server_already && dhcp_server_details" class="mt-4">
          <v-col cols="12">
            <v-card v-if="dhcp_server_details?.leases.length === 0 && !loading_leases" flat>
              <v-card-title
                class="text-h6 py-2 not-selectable"
              >
                {{
                  dhcp_server_details?.is_backup && !dhcp_server_details?.is_running
                    ? 'DHCP Server in backup' : 'No DHCP leases found'
                }}
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
            </v-card>
            <v-card v-else flat>
              <v-card-title
                class="text-h6 py-2 cursor-pointer not-selectable"
                @click="toggleLeasesExpanded"
              >
                <v-icon
                  :class="{ 'rotate-180': leases_expanded }"
                  class="transition-transform mr-2"
                >
                  mdi-chevron-down
                </v-icon>
                DHCP leases
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
                      :items="dhcp_server_details?.leases"
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
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en.json'
import Vue, { PropType } from 'vue'

import beacon from '@/store/beacon'
import ethernet from '@/store/ethernet'
import {
  AddressMode, DHCPServerDetails, DHCPServerLease, EthernetInterface,
} from '@/types/ethernet'

import AddressCreationDialog from './AddressCreationDialog.vue'
import AddressDeletionDialog from './AddressDeletionDialog.vue'
import DHCPServerDialog from './DHCPServerDialog.vue'

TimeAgo.addDefaultLocale(en)
const timeAgo = new TimeAgo('en-US')

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
      dhcp_server_details: undefined as DHCPServerDetails | undefined,
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

      await ethernet.deleteAddress({ interface_name: this.adapter.name, ip_address: ip })
    },
    async triggerForDynamicIP(): Promise<void> {
      ethernet.setUpdatingInterfaces(true)

      await ethernet.triggerDynamicIP(this.adapter.name)
    },
    openDHCPServerDialog(): void {
      this.show_dhcp_server_dialog = true
    },
    async removeDHCPServer(): Promise<void> {
      ethernet.setUpdatingInterfaces(true)

      await ethernet.RemoveDHCPServer(this.adapter.name)
    },
    async fetchLeases(): Promise<void> {
      if (!this.is_there_dhcp_server_already) {
        this.dhcp_server_details = undefined
        return
      }

      this.loading_leases = true
      try {
        const response = await ethernet.getDHCPServerDetails(this.adapter.name)
        this.dhcp_server_details = response.data[this.adapter.name] as DHCPServerDetails
        this.dhcp_server_details.leases = this.dhcp_server_details?.leases.map((lease: DHCPServerLease) => ({
          ...lease,
          expires_at: lease.expires_at ? new Date(lease.expires_at) : undefined,
          is_active: lease.expires_epoch ? lease.expires_epoch > Date.now() / 1000 : false,
        }))
      } catch (error) {
        console.error(`Failed to fetch DHCP Server details for interface: ${this.adapter.name}`, error)
        this.dhcp_server_details = undefined
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
    formatLeaseExpiry(expiresAt?: Date): string {
      if (expiresAt === undefined) {
        return 'Unknown'
      }

      const now = new Date()
      const diffMs = expiresAt.getTime() - now.getTime()

      if (diffMs < 0) {
        return 'Expired'
      }

      return timeAgo.format(expiresAt, 'round')
    },
    getLeaseExpiryClass(lease: DHCPServerLease): string {
      const now = new Date()
      const diffMs = lease.expires_at ? lease.expires_at.getTime() - now.getTime() : 0

      if (lease.expires_at === undefined || diffMs < 0) {
        return 'error--text'
      }
      if (diffMs < 1000 * 60 * 60) {
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

.not-selectable {
  user-select: none;
}

.rotate-180 {
  transform: rotate(180deg);
}

.transition-transform {
  transition: transform 0.2s ease;
}
</style>
