<template>
  <v-dialog
    width="350"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>New IP address on '{{ interfaceName }}'</v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-select
            v-model="mode"
            :items="mode_types"
            label="Mode"
            :rules="[validate_required_field]"
          />

          <v-text-field
            v-model="ip_address"
            :rules="[is_valid_ip_input]"
            :disabled="!editable_ip"
            label="IP address"
          />

          <v-btn
            color="success"
            class="mr-4"
            @click="createNewAddress"
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

import ethernet from '@/store/ethernet'
import notifications from '@/store/notifications'
import { AddressMode } from '@/types/ethernet'
import { ethernet_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'
import { isIpAddress, isNotEmpty } from '@/utils/pattern_validators'

export default Vue.extend({
  name: 'NetworkCard',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    interfaceName: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      mode: AddressMode.unmanaged,
      ip_address: '',
    }
  },

  computed: {
    mode_types(): {value: AddressMode, text: string}[] {
      return Object.entries(AddressMode).map(
        (mode) => ({ value: mode[1], text: this.showable_mode_name(mode[1]) }),
      )
    },
    editable_ip(): boolean {
      return this.mode === AddressMode.unmanaged
    },
    form(): VForm {
      return this.$refs.form as VForm
    },
  },
  watch: {
    show(val: boolean): void {
      if (val === false) {
        this.mode = AddressMode.unmanaged
        this.ip_address = ''
      }
    },
  },
  methods: {
    validate_required_field(input: string): (true | string) {
      return isNotEmpty(input) ? true : 'Required field.'
    },
    is_valid_ip_input(input: string): (true | string) {
      if (this.mode === AddressMode.unmanaged) {
        return isIpAddress(input) ? true : 'Invalid IP address.'
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
    async createNewAddress(): Promise<boolean> {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }
      ethernet.setUpdatingInterfaces(true)
      this.showDialog(false)

      await back_axios({
        method: 'post',
        url: `${ethernet.API_URL}/address`,
        timeout: 10000,
        params: {
          interface_name: this.interfaceName,
          mode: this.mode,
          ip_address: this.ip_address === '' ? null : this.ip_address,
        },
      })
        .then(() => {
          this.form.reset()
        })
        .catch((error) => {
          const message = `Could not create new address on ${this.interfaceName}: ${error.message}.`
          notifications.pushError({ service: ethernet_service, type: 'ETHERNET_ADDRESS_CREATION_FAIL', message })
        })
      return true
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>
