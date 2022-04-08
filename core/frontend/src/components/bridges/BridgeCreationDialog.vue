<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        New bridge
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-select
            v-model="bridge.serial_path"
            :items="available_serial_ports"
            :label="serial_selector_label"
            :rules="[validate_required_field, is_path]"
            no-data-text="No serial ports available"
            :loading="updating_serial_ports"
          />

          <v-select
            v-model="bridge.baud"
            :items="available_baudrates"
            label="Serial baudrate"
            :rules="[validate_required_field, is_baudrate]"
          />

          <v-text-field
            v-model="bridge.ip"
            :rules="[validate_required_field, is_ip_address]"
            label="IP address"
          />

          <v-text-field
            v-model="bridge.udp_port"
            :counter="50"
            label="UDP port"
            :rules="[validate_required_field, is_socket_port]"
          />

          <v-btn
            color="success"
            class="mr-4"
            @click="createBridge"
          >
            Create
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import Notifier from '@/libs/notifier'
import bridget from '@/store/bridget'
import { Baudrate } from '@/types/common'
import { bridget_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'
import {
  isBaudrate, isFilepath, isIntegerString, isIpAddress, isNotEmpty, isSocketPort,
} from '@/utils/pattern_validators'

const notifier = new Notifier(bridget_service)

export default Vue.extend({
  name: 'BridgeCreationDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
  },

  data() {
    return {
      bridge: {
        serial_path: '',
        baud: null as (number | null),
        ip: '0.0.0.0',
        udp_port: '15000',
      },
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    available_baudrates(): {value: number, text: string}[] {
      return Object.entries(Baudrate).map(
        (baud) => ({ value: parseInt(baud[1], 10), text: baud[1] }),
      )
    },
    available_serial_ports(): {value: string, text: string}[] {
      return bridget.available_serial_ports.map(
        (port) => ({ value: port, text: port }),
      )
    },
    updating_serial_ports(): boolean {
      return bridget.updating_serial_ports
    },
    serial_selector_label(): string {
      return this.updating_serial_ports ? 'Fetching available serial ports...' : 'Serial port'
    },
  },
  methods: {
    validate_required_field(input: string | number): (true | string) {
      const string_input = String(input)
      return isNotEmpty(string_input) ? true : 'Required field.'
    },
    is_ip_address(input: string): (true | string) {
      return isIpAddress(input) ? true : 'Invalid IP.'
    },
    is_path(input: string): (true | string) {
      return isFilepath(input) ? true : 'Invalid path.'
    },
    is_socket_port(input: string): (true | string) {
      if (!isIntegerString(input)) {
        return 'Please use an integer value.'
      }
      const int_input = parseInt(input, 10)
      return isSocketPort(int_input) ? true : 'Invalid port.'
    },
    is_baudrate(input: number): (true | string) {
      return isBaudrate(input) ? true : 'Invalid baudrate.'
    },
    async createBridge(): Promise<boolean> {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }

      bridget.setUpdatingBridges(true)
      this.showDialog(false)

      await back_axios({
        method: 'post',
        url: `${bridget.API_URL}/bridges`,
        timeout: 10000,
        data: this.bridge,
      })
        .then(() => {
          this.form.reset()
        })
        .catch((error) => {
          notifier.pushBackError('BRIDGE_CREATE_FAIL', error)
        })
      return true
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>

<style>
</style>
