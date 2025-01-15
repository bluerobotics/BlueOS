<template>
  <div class="master-endpoint-manager d-flex flex-column align-center">
    <v-card
      width="100%"
      class="pa-4"
    >
      <v-card-title class="text-h6 mb-2">
        Master Endpoint Configuration
      </v-card-title>

      <v-form
        ref="form"
        v-model="form_valid"
        lazy-validation
      >
        <v-select
          v-model="endpoint.connection_type"
          :items="endpoint_types"
          label="Connection Type"
          :rules="[validate_required_field]"
          @change="updateDefaultPlace"
        />

        <v-text-field
          v-model="endpoint.place"
          :rules="[validate_required_field, is_ip_address_path, is_useable_ip_address]"
          label="IP/Device"
        />

        <v-text-field
          v-model.number="endpoint.argument"
          label="Port/Baudrate"
          :rules="[is_socket_port_baudrate]"
        />

        <v-card-actions class="mt-4">
          <v-spacer />
          <v-btn
            color="primary"
            :loading="saving"
            :disabled="!form_valid || !has_changes"
            @click="saveEndpoint"
          >
            Save Changes
          </v-btn>
        </v-card-actions>
      </v-form>
    </v-card>

    <v-snackbar
      v-model="show_success"
      color="success"
      timeout="3000"
    >
      Master endpoint updated successfully
      <template #action="{ attrs }">
        <v-btn
          text
          v-bind="attrs"
          @click="show_success = false"
        >
          Close
        </v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import beacon from '@/store/beacon'
import { AutopilotEndpoint, EndpointType, userFriendlyEndpointType } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'
import {
  isBaudrate, isFilepath, isIpAddress, isNotEmpty, isSocketPort,
} from '@/utils/pattern_validators'

const notifier = new Notifier(autopilot_service)

const defaultEndpoint: AutopilotEndpoint = {
  name: 'master',
  owner: 'User',
  connection_type: EndpointType.udpin,
  place: '0.0.0.0',
  argument: 14551,
  persistent: true,
  protected: false,
  enabled: true,
}

export default Vue.extend({
  name: 'MasterEndpointManager',
  data() {
    return {
      form_valid: true,
      saving: false,
      show_success: false,
      original_endpoint: { ...defaultEndpoint },
      endpoint: { ...defaultEndpoint },
    }
  },
  computed: {
    endpoint_types(): {value: EndpointType, text: string}[] {
      return Object.entries(EndpointType).map(
        (type) => ({ value: type[1], text: userFriendlyEndpointType(type[1]) }),
      )
    },
    form(): VForm {
      return this.$refs.form as VForm
    },
    user_ip_address(): string {
      return beacon.client_ip_address
    },
    available_ips(): string[] {
      return [...new Set(beacon.available_domains.map((domain) => domain.ip))]
    },
    has_changes(): boolean {
      return this.endpoint.connection_type !== this.original_endpoint.connection_type
        || this.endpoint.place !== this.original_endpoint.place
        || this.endpoint.argument !== this.original_endpoint.argument
    },
  },
  mounted() {
    this.fetchCurrentEndpoint()
  },
  methods: {
    validate_required_field(input: string): (true | string) {
      return isNotEmpty(input) ? true : 'Required field.'
    },
    is_ip_address_path(input: string): (true | string) {
      return isIpAddress(input) || isFilepath(input) ? true : 'Invalid IP/Device-path.'
    },
    is_useable_ip_address(input: string): (true | string) {
      if ([EndpointType.udpin, EndpointType.tcpin].includes(this.endpoint.connection_type)) {
        if (!['0.0.0.0', ...this.available_ips].includes(input)) {
          return 'This IP is not available at any of the network interfaces.'
        }
      }
      if ([EndpointType.udpout, EndpointType.tcpout].includes(this.endpoint.connection_type)) {
        if (input === '0.0.0.0') return '0.0.0.0 as a client is undefined behavior.'
      }
      return true
    },
    is_socket_port_baudrate(input: number): (true | string) {
      if (typeof input === 'string') {
        return 'Please use an integer value.'
      }
      return isSocketPort(input) || isBaudrate(input) ? true : 'Invalid Port/Baudrate.'
    },
    updateDefaultPlace(): void {
      switch (this.endpoint.connection_type) {
        case EndpointType.udpin:
        case EndpointType.tcpin:
          this.endpoint.place = '0.0.0.0'
          break
        case EndpointType.udpout:
        case EndpointType.tcpout:
          this.endpoint.place = this.user_ip_address
          break
        default:
          this.endpoint.place = '/dev/ttyAMA1' // Serial3
      }
    },
    async fetchCurrentEndpoint(): Promise<void> {
      try {
        const response = await back_axios({
          method: 'get',
          url: `${autopilot.API_URL}/endpoints/manual_board_master_endpoint`,
          timeout: 10000,
        })
        const endpoint_data = {
          ...defaultEndpoint,
          ...response.data,
        }
        this.endpoint = { ...endpoint_data }
        this.original_endpoint = { ...endpoint_data }
      } catch (error) {
        notifier.pushBackError('MASTER_ENDPOINT_FETCH_FAIL', error)
      }
    },
    async saveEndpoint(): Promise<void> {
      if (!this.form.validate()) {
        return
      }

      this.saving = true
      try {
        await back_axios({
          method: 'post',
          url: `${autopilot.API_URL}/endpoints/manual_board_master_endpoint`,
          timeout: 10000,
          data: this.endpoint,
        })
        this.original_endpoint = { ...this.endpoint }
        this.show_success = true
      } catch (error) {
        notifier.pushBackError('MASTER_ENDPOINT_SAVE_FAIL', error)
      } finally {
        this.saving = false
      }
    },
  },
})
</script>

<style scoped>
.master-endpoint-manager {
  width: 100%;
  max-width: 600px;
  margin: 0 auto;
}
</style>
