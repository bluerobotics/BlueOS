<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        New endpoint
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-text-field
            v-model="endpoint.name"
            :counter="50"
            label="Name"
            :rules="[validate_required_field]"
          />

          <v-text-field
            v-model="endpoint.owner"
            :counter="50"
            label="Owner"
            :rules="[validate_required_field]"
          />

          <v-select
            v-model="endpoint.connection_type"
            :items="endpoint_types"
            label="Type"
            :rules="[validate_required_field]"
          />

          <v-text-field
            v-model="endpoint.place"
            :rules="[validate_required_field, is_ip_address_path]"
            label="IP/Device"
          />

          <v-text-field
            v-model="endpoint.argument"
            :counter="50"
            label="Port/Baudrate"
            :rules="[validate_required_field, is_socket_port_baudrate]"
          />

          <v-checkbox
            v-model="endpoint.persistent"
            label="Save endpoint between system sessions?"
          />

          <v-checkbox
            v-model="endpoint.protected"
            label="Protect endpoint from being deleted?"
            disabled
          />

          <v-btn
            color="success"
            class="mr-4"
            @click="createEndpoint"
          >
            Create
          </v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import axios from 'axios'
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'
import notifications from '@/store/notifications'
import { EndpointType, userFriendlyEndpointType } from '@/types/autopilot'
import { autopilot_manager_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { VForm } from '@/types/vuetify'
import {
  isBaudrate, isFilepath, isIntegerString, isIpAddress, isNotEmpty, isSocketPort,
} from '@/utils/pattern_validators'

export default Vue.extend({
  name: 'ConnectionDialog',
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
      endpoint: {
        name: '',
        owner: '',
        connection_type: EndpointType.udpin,
        place: '',
        argument: '',
        protected: false,
        persistent: false,
      },
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
  },
  methods: {
    validate_required_field(input: string): (true | string) {
      return isNotEmpty(input) ? true : 'Required field.'
    },
    is_ip_address_path(input: string): (true | string) {
      return isIpAddress(input) || isFilepath(input) ? true : 'Invalid IP/Device-path.'
    },
    is_socket_port_baudrate(input: string): (true | string) {
      if (!isIntegerString(input)) {
        return 'Please use an integer value.'
      }
      const int_input = parseInt(input, 10)
      return isSocketPort(int_input) || isBaudrate(int_input) ? true : 'Invalid Port/Baudrate.'
    },
    async createEndpoint(): Promise<boolean> {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }

      autopilot.setUpdatingEndpoints(true)
      this.showDialog(false)

      await axios({
        method: 'post',
        url: `${autopilot.API_URL}/endpoints`,
        timeout: 10000,
        data: [this.endpoint],
      })
        .then(() => {
          this.form.reset()
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            autopilot_manager_service,
            'AUTOPILOT_ENDPOINT_CREATE_FAIL',
            `Could not create endpoint: ${error.message}.`,
          ))
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
