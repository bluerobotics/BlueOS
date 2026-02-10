<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        Endpoint
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-text-field
            v-model="edited_endpoint.name"
            :counter="50"
            label="Name"
            :disabled="edit"
            :hint="edit ? 'Cannot edit name. If needed, create a new endpoint.' : 'Indicates endpoint usage.'"
            :persistent-hint="edit"
            :rules="[validate_required_field]"
          />

          <v-text-field
            v-model="edited_endpoint.owner"
            :counter="50"
            label="Owner"
            hint="Helps identifying who created this endpoint."
            :rules="[validate_required_field]"
          />

          <v-select
            v-model="edited_endpoint.connection_type"
            :items="endpoint_types"
            label="Type"
            :rules="[validate_required_field]"
            @change="updateIp"
          />

          <v-text-field
            v-model="edited_endpoint.place"
            :rules="[validate_required_field, is_ip_address_path, is_useable_ip_address]"
            label="IP/Device"
          />

          <v-text-field
            v-model.number="edited_endpoint.argument"
            :counter="50"
            label="Port/Baudrate"
            :rules="[is_socket_port_baudrate]"
          />

          <v-checkbox
            v-model="edited_endpoint.persistent"
            label="Save endpoint between system sessions"
          />

          <v-checkbox
            v-model="edited_endpoint.protected"
            label="Protect endpoint from being deleted"
            disabled
          />

          <v-checkbox
            v-model="edited_endpoint.enabled"
            label="Start endpoint already enabled"
          />

          <v-row class="mt-2">
            <v-btn
              color="primary"
              class="ml-3"
              @click="showDialog(false)"
            >
              Cancel
            </v-btn>

            <v-spacer />

            <v-btn
              color="primary mr-3"
              @click="createEditEndpoint"
            >
              {{ edit ? 'Update endpoint' : 'Create endpoint' }}
            </v-btn>
          </v-row>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import autopilot from '@/store/autopilot_manager'
import beacon from '@/store/beacon'
import { AutopilotEndpoint, EndpointType, userFriendlyEndpointType } from '@/types/autopilot'
import { VForm } from '@/types/vuetify'
import {
  isBaudrate, isFilepath, isIpAddress, isNotEmpty, isSocketPort,
} from '@/utils/pattern_validators'

const defaultEndpointValue: AutopilotEndpoint = {
  name: 'My endpoint',
  owner: 'User',
  connection_type: EndpointType.udpout,
  place: '0.0.0.0',
  argument: 14550,
  protected: false,
  persistent: true,
  enabled: true,
}

export default Vue.extend({
  name: 'EndpointCreationDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    edit: {
      type: Boolean,
      default: false,
    },
    baseEndpoint: {
      type: Object as PropType<AutopilotEndpoint>,
      required: false,
      default() {
        return defaultEndpointValue
      },
    },
  },

  data() {
    return {
      edited_endpoint: this.baseEndpoint,
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
    connection_type(): EndpointType {
      return this.edited_endpoint.connection_type
    },
  },
  watch: {
    connection_type() {
      this.form.validate()
    },
    baseEndpoint: {
      deep: true,
      immediate: true,
      handler(newValue) {
        this.edited_endpoint = { ...newValue }
      },
    },
    show: {
      deep: true,
      immediate: true,
      handler(newValue) {
        if (newValue && !this.edit) {
          this.edited_endpoint = { ...defaultEndpointValue }
        }
      },
    },
  },
  methods: {
    validate_required_field(input: string): (true | string) {
      return isNotEmpty(input) ? true : 'Required field.'
    },
    is_ip_address_path(input: string): (true | string) {
      return isIpAddress(input) || isFilepath(input) ? true : 'Invalid IP/Device-path.'
    },
    is_useable_ip_address(input: string): (true | string) {
      if ([EndpointType.udpin, EndpointType.tcpin].includes(this.edited_endpoint.connection_type)) {
        if (!['0.0.0.0', ...this.available_ips].includes(input)) {
          return 'This IP is not available at any of the network interfaces.'
        }
      }
      if ([EndpointType.udpout, EndpointType.tcpout].includes(this.edited_endpoint.connection_type)) {
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
    createEditEndpoint(): boolean {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }

      autopilot.setUpdatingEndpoints(true)
      this.showDialog(false)

      this.$emit('endpointChange', this.edited_endpoint)
      return true
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
    updateIp() {
      switch (this.edited_endpoint.connection_type) {
        case EndpointType.udpin:
        case EndpointType.tcpin:
          this.edited_endpoint.place = '0.0.0.0'
          break
        case EndpointType.udpout:
        case EndpointType.tcpout:
          this.edited_endpoint.place = this.user_ip_address
          break
        default:
          this.edited_endpoint.place = '/dev/ttyAMA1' // Serial3
      }
    },
  },
})
</script>
