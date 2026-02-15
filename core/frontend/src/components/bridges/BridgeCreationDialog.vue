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
            item-text="name"
            :item-value="(item) => item.by_path ? item.by_path : item.name"
            :item-disabled="(item) => item.current_user !== null"
            dense
          >
            <template #item="{ item }">
              <v-list
                fluid
                max-width="400"
                ripple
                @mousedown.prevent
              >
                <v-list-item dense>
                  <v-list-item-content dense>
                    <v-list-item-title md-1>
                      Device: {{ item.name }}
                      <v-chip
                        v-if="item.current_user"
                        class="ma-2 pl-2 pr-2"
                        color="red"
                        pill
                        x-small
                        text-color="white"
                      >
                        In use by {{ item.current_user }}
                      </v-chip>
                    </v-list-item-title>
                    <v-list-item-subtitle class="text-wrap">
                      Path: {{ item.by_path ? item.by_path : item.name }}
                    </v-list-item-subtitle>
                    <v-list-item-subtitle
                      v-if="item.by_path_created_ms_ago"
                      class="text-wrap"
                    >
                      Created: {{ create_time_ago(item.by_path_created_ms_ago) }}
                    </v-list-item-subtitle>
                    <div
                      v-if="item.udev_properties && item.udev_properties['ID_VENDOR']"
                    >
                      <v-list-item-subtitle class="text-wrap">
                        Info: {{ item.udev_properties["ID_VENDOR"] }} / {{ item.udev_properties["ID_MODEL"] }}
                      </v-list-item-subtitle>
                    </div>
                    <device-path-helper
                      v-if="item.name.startsWith('/dev')"
                      class="mr-5"
                      inline
                      :height="'150px'"
                      :width="'150px'"
                      :device="item.name"
                    />
                  </v-list-item-content>
                </v-list-item>
              </v-list>
            </template>
          </v-select>

          <v-select
            v-model="bridge.baud"
            :items="available_baudrates"
            label="Serial baudrate"
            :rules="[validate_required_field, is_baudrate]"
          />
          <v-tabs
            v-model="tab"
            fixed-tabs
          >
            <v-tab @click="bridge.udp_listen_port = 15000">
              Server Mode
            </v-tab>
            <v-tab @click="bridge.udp_listen_port = 0">
              Client Mode
            </v-tab>
          </v-tabs>
          <span v-if="mode === 'server'">
            Server mode will bind to the given port at the BlueOS device.
            This means it will receive data from the topside computer at port
            <B>{{ bridge.udp_listen_port }}</B>, and will send data back
            to the topside computer at the port where the data originated at the topside computer.
          </span>
          <span v-else-if="mode === 'client'">
            Client mode will send data to the given IP address and port.
            This means it will send data to the topside computer at IP
            <B>{{ bridge.ip }}</B> and port <B>{{ bridge.udp_target_port }}</B>.
            It will receive data back from the topside computer at
            <b>{{ bridge.udp_listen_port ? `port ${bridge.udp_listen_port}` : 'an automatically assigned port' }}</b>.
          </span>
          <v-text-field
            v-model="bridge.ip"
            :rules="[validate_required_field, is_ip_address]"
            :label="'IP address ' + bridge_mode"
          />

          <v-text-field
            v-model.number="bridge.udp_listen_port"
            :counter="50"
            :label="`Vehicle/Server port ${bridge.udp_listen_port == 0 ? '(Automatic)' : '' }`"
            :rules="[validate_required_field, is_socket_auto_port]"
            type="number"
          />

          <v-text-field
            v-if="mode === 'client'"
            v-model="bridge.udp_target_port"
            :counter="50"
            :label="`Topside/Target port`"
            :rules="[validate_required_field, is_socket_port]"
            type="number"
          />
        </v-form>
      </v-card-text>
      <v-card-actions
        class="pt-1"
      >
        <v-btn
          color="primary"
          @click="showDialog(false)"
        >
          Cancel
        </v-btn>

        <v-spacer />

        <v-btn
          color="primary"
          @click="createBridge"
        >
          Create
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import { formatDistanceToNow } from 'date-fns'
import Vue from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import DevicePathHelper from '@/components/common/DevicePathHelper.vue'
import Notifier from '@/libs/notifier'
import autopilot from '@/store/autopilot_manager'
import bridget from '@/store/bridget'
import system_information from '@/store/system-information'
import { Baudrate } from '@/types/common'
import { bridget_service } from '@/types/frontend_services'
import { SerialPortInfo } from '@/types/system-information/serial'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'
import {
  isBaudrate,
  isFilepath,
  isIpAddress,
  isNotEmpty,
  isSocketPort,
} from '@/utils/pattern_validators'

const notifier = new Notifier(bridget_service)

export default Vue.extend({
  name: 'BridgeCreationDialog',
  components: {
    DevicePathHelper,
  },
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
      tab: 0,
      bridge: {
        serial_path: '',
        baud: null as (number | null),
        ip: '0.0.0.0',
        udp_target_port: 15000,
        udp_listen_port: 15000,
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
    mode(): string {
      switch (this.tab) {
        case 0:
          return 'server'
        case 1:
          return 'client'
        default:
          return 'server'
      }
    },

    available_serial_ports(): SerialPortInfo[] {
      const system_serial_ports: SerialPortInfo[] | undefined = system_information.serial?.ports
      if (!system_serial_ports) {
        return []
      }
      return system_serial_ports
        .filter((serial_info) => bridget.available_serial_ports.includes(serial_info.name))
        .map((serial_info) => ({
          ...serial_info,
          current_user: autopilot.autopilot_serials.some(
            (serial) => serial.endpoint === serial_info.name,
          ) ? 'autopilot' : null,
        }))
    },
    bridge_mode(): string {
      switch (this.bridge.ip) {
        case '127.0.0.1':
          return '(Server mode, local only)'
        case '0.0.0.0':
          return '(Server mode)'
        default:
          if (this.is_ip_address(this.bridge.ip) === true) {
            return '(Client mode)'
          }
          return ''
      }
    },
    updating_serial_ports(): boolean {
      return bridget.updating_serial_ports
    },
    serial_selector_label(): string {
      return this.updating_serial_ports ? 'Fetching available serial ports...' : 'Serial port'
    },
  },
  async mounted() {
    await AutopilotManager.fetchAutopilotSerialConfiguration()
  },
  methods: {
    create_time_ago(ms_time: number): string {
      const time_now = new Date().valueOf()
      const creation_time = time_now - ms_time
      const creation_date = new Date(creation_time)
      return `${formatDistanceToNow(creation_time)} ago (${creation_date.toLocaleTimeString()})`
    },
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
      const int_input = parseInt(input, 10)
      return isSocketPort(int_input) ? true : 'Invalid port.'
    },
    is_socket_auto_port(input: string): (true | string) {
      const int_input = parseInt(input, 10)
      if (this.mode === 'client' && int_input === 0) {
        return true
      }
      return this.is_socket_port(input)
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
      this.bridge.udp_listen_port = parseInt(String(this.bridge.udp_listen_port), 10)
      this.bridge.udp_target_port = parseInt(String(this.bridge.udp_target_port), 10)

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
