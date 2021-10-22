<template>
  <v-dialog
    width="500"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        New NMEA socket
      </v-card-title>

      <v-card-text class="d-flex flex-column">
        <v-form
          ref="form"
          lazy-validation
        >
          <v-select
            v-model="nmea_socket.kind"
            :items="available_socket_kinds"
            label="Socket kind"
            :rules="[validate_required_field]"
            no-data-text="No serial ports available"
            :loading="updating_serial_ports"
          />

          <v-text-field
            v-model="nmea_socket.port"
            :rules="[validate_required_field, is_socket_port]"
            label="Socket port"
          />

          <v-text-field
            v-model="nmea_socket.component_id"
            :counter="3"
            label="Mavlink component ID"
            :rules="[validate_required_field, is_component_id]"
          />

          <v-btn
            color="success"
            class="mr-4"
            @click="createNMEASocket"
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

import nmea_injector from '@/store/nmea-injector'
import notifications from '@/store/notifications'
import { SocketKind } from '@/types/common'
import { nmea_injector_service } from '@/types/frontend_services'
import { LiveNotification, NotificationLevel } from '@/types/notifications'
import { VForm } from '@/types/vuetify'
import {
  isIntegerString, isNotEmpty, isSocketPort,
} from '@/utils/pattern_validators'

export default Vue.extend({
  name: 'NMEASocketCreationDialog',
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
      nmea_socket: {
        kind: SocketKind.UDP,
        port: '27000',
        component_id: '220', // MAV_COMPONENT ID of 220 refers to MAV_COMP_ID_GPS #1, usually used for external GPSs
      },
    }
  },
  computed: {
    form(): VForm {
      return this.$refs.form as VForm
    },
    available_socket_kinds(): {value: SocketKind, text: string}[] {
      return Object.entries(SocketKind).map(
        (kind) => ({ value: kind[1], text: kind[0] }),
      )
    },
  },
  methods: {
    validate_required_field(input: string | number): (true | string) {
      const string_input = String(input)
      return isNotEmpty(string_input) ? true : 'Required field.'
    },
    is_socket_port(input: string): (true | string) {
      if (!isIntegerString(input)) {
        return 'Please use an integer value.'
      }
      const int_input = parseInt(input, 10)
      return isSocketPort(int_input) ? true : 'Invalid port.'
    },
    is_component_id(input: string): (true | string) {
      if (!isIntegerString(input)) {
        return 'Please use an integer value.'
      }
      const int_input = parseInt(input, 10)
      // Mavlink MAV_COMPONENT IDs range from 25 to 250: https://mavlink.io/en/messages/minimal.html#MAV_COMPONENT
      const is_in_id_range = int_input >= 25 && int_input <= 250
      return is_in_id_range ? true : 'Please use a valid component ID (check Mavlink documentation for valid IDs).'
    },
    async createNMEASocket(): Promise<boolean> {
      // Validate form before proceeding with API request
      if (!this.form.validate()) {
        return false
      }

      nmea_injector.setUpdatingNMEASockets(true)
      this.showDialog(false)

      await axios({
        method: 'post',
        url: `${nmea_injector.API_URL}/socks`,
        timeout: 10000,
        data: this.nmea_socket,
      })
        .then(() => {
          this.form.reset()
        })
        .catch((error) => {
          notifications.pushNotification(new LiveNotification(
            NotificationLevel.Error,
            nmea_injector_service,
            'NMEA_SOCKET_CREATE_FAIL',
            `Could not create NMEA socket: ${error.message}.`,
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
