<template>
  <v-dialog
    width="350"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>New static IP address on '{{ interfaceName }}'</v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
          @submit.prevent="createNewAddress"
        >
          <v-text-field
            v-model="ip_address"
            :rules="[is_valid_ip_input]"
            label="IP address"
          />

          <v-btn
            color="primary"
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
import { VForm } from '@/types/vuetify'
import { isIpAddress } from '@/utils/pattern_validators'

export default Vue.extend({
  name: 'AddressCreationDialog',
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
      ip_address: '',
    }
  },

  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
  },
  watch: {
    show(val: boolean): void {
      if (val === false) {
        this.ip_address = ''
      }
    },
  },
  methods: {
    is_valid_ip_input(input: string): (true | string) {
      return isIpAddress(input) ? true : 'Invalid IP address.'
    },
    async createNewAddress(): Promise<boolean> {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }
      this.showDialog(false)

      await ethernet.addAddress({ interface_name: this.interfaceName, ip_address: this.ip_address })
        .then(() => {
          this.form.reset()
        })
      return true
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
  },
})
</script>
