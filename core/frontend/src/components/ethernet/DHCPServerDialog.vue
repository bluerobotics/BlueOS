<template>
  <v-dialog
    width="350"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        DHCP Server for interface '{{ adapter.name }}'
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-select
          v-model="selected_ip"
          required
          :items="available_static_ips"
          label="Server Gateway"
        />

        <v-checkbox
          v-model="is_backup_server"
          label="Backup Server"
        />
        <v-alert
          type="info"
          dense
          text
          class="mt-0"
        >
          When Backup Server is enabled, the DHCP server will stay inactive and only
          start serving IP addresses if no other DHCP server is detected on the network.
        </v-alert>
        <v-btn
          :disabled="!allow_enabling"
          color="primary"
          @click="addDHCPServer"
        >
          Enable
        </v-btn>
      </v-card-text>

      <v-card-text v-if="enabling_dhcp">
        Enabling DHCP server, please wait...
        <v-progress-linear
          indeterminate
          color="primary"
          class="mb-0"
        />
      </v-card-text>

      <v-card-text v-if="tried_enabling">
        <v-alert
          :type="connection_result_type"
          class="mx-1"
        >
          {{ connection_result_message }}
        </v-alert>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import ethernet from '@/store/ethernet'
import { AddressMode, EthernetInterface } from '@/types/ethernet'

enum ServerCreationStatus {
  NotStarted,
  Enabling,
  Succeeded,
  Failed
}

export default Vue.extend({
  name: 'DHCPServerDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    adapter: {
      type: Object as PropType<EthernetInterface>,
      required: true,
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      creation_status: ServerCreationStatus.NotStarted,
      connection_result_message: '',
      selected_ip: '',
      is_backup_server: false,
    }
  },
  computed: {
    available_static_ips(): { value: string, text: string }[] {
      return this.adapter.addresses
        .filter((address) => address.mode === AddressMode.unmanaged)
        .map((address) => ({ value: address.ip, text: address.ip }))
    },
    allow_enabling(): boolean {
      return this.selected_ip !== '' && this.creation_status !== ServerCreationStatus.Enabling
    },
    tried_enabling(): boolean {
      return [ServerCreationStatus.Succeeded, ServerCreationStatus.Failed].includes(this.creation_status)
    },
    connection_result_type(): string {
      switch (this.creation_status) {
        case ServerCreationStatus.Succeeded:
          return 'success'
        case ServerCreationStatus.Failed:
          return 'error'
        default:
          return 'info'
      }
    },
    enabling_dhcp(): boolean {
      return this.creation_status === ServerCreationStatus.Enabling
    }
    ,
  },
  watch: {
    show(val: boolean): void {
      if (val === false) {
        this.creation_status = ServerCreationStatus.NotStarted
        this.connection_result_message = ''
        this.selected_ip = ''
      }
    },
  },
  methods: {
    async addDHCPServer(): Promise<void> {
      this.creation_status = ServerCreationStatus.Enabling
      this.connection_result_message = ''

      await ethernet.addDHCPServer({
        interface_name: this.adapter.name,
        ipv4_gateway: this.selected_ip,
        is_backup_server: this.is_backup_server,
      })
        .then(() => {
          this.creation_status = ServerCreationStatus.Succeeded
          this.connection_result_message = 'Successfully enabled DHCP server.'
        })
        .catch((error) => {
          const message = error.response?.data?.detail ?? error.message
          this.connection_result_message = message
        })
    },

    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>
