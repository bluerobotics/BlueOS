<template>
  <v-card
    class="v-card v-sheet theme--light mt-5"
  >
    <v-combobox
      v-for="port in Object.keys(port_map)"
      :key="port"
      v-model="ports[port]"
      :items="available_ports"
      :label="`${port_map[port]}`"
      :rules="[isValidEndpoint]"
      :loading="current_serial_ports.isEmpty()"
      outlined
      dense
    >
      <template #item="data">
        <v-chip
          :key="JSON.stringify(data.item)"
          v-bind="data.attrs"
          :input-value="data.selected"
          style="height: 150px; position: relative;"
          @click:close="data.parent.selectItem(data.item)"
        >
          <device-path-helper
            class="mr-5"
            inline
            :height="'150px'"
            :device="data.item"
          />
          {{ data.item }}
        </v-chip>
      </template>
      <template #selection="{ attrs, item, parent }">
        <v-chip
          :key="item"
          v-bind="attrs"
          small
        >
          {{ item }}
          <v-icon
            class="ml-1"
            small
            @click="parent.reset()"
          >
            $delete
          </v-icon>
        </v-chip>
        <device-path-helper
          v-if="item.startsWith('/dev')"
          :device="item"
        />
      </template>
    </v-combobox>
    <v-card-actions>
      <v-btn
        style="margin: auto;"
        color="primary"
        :loading="restarting"
        @click="saveAndRestart"
      >
        Save and restart
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import DevicePathHelper from '@/components/common/DevicePathHelper.vue'
import { OneMoreTime } from '@/one-more-time'
import autopilot from '@/store/autopilot_manager'
import system_information from '@/store/system-information'
import { SerialEndpoint } from '@/types/autopilot'
import { Dictionary } from '@/types/common'
import back_axios from '@/utils/api'
import { isIpAddress } from '@/utils/pattern_validators'

import { fetchAutopilotSerialConfiguration } from './AutopilotManagerUpdater'

export default Vue.extend({
  name: 'AutopilotSerialConfiguration',
  components: {
    DevicePathHelper,
  },
  data() {
    return {
      // Portmap is used to deal with ardupilots weird mapping situation
      // Note that the mapping is not linear
      port_map: {
        // A (Serial 0) is reserved
        C: 'Serial 1',
        D: 'Serial 2',
        B: 'Serial 3',
        E: 'Serial 4',
        F: 'Serial 5',
        G: 'Serial 6',
        H: 'Serial 7',
        I: 'Serial 8',
      },
      ports: {} as Dictionary<string | undefined>,
      fetch_autopilot_serial_config_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_serial_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  computed: {
    restarting(): boolean {
      return autopilot.restarting
    },
    current_serial_ports(): SerialEndpoint[] {
      return autopilot.autopilot_serials
    },
    available_ports(): string[] {
      return system_information.serial?.ports?.map((port) => port.by_path ?? port.name) ?? []
    },
    new_data(): SerialEndpoint[] {
      const new_list = [] as SerialEndpoint[]
      for (const [port, endpoint] of Object.entries(this.ports)) {
        if (endpoint && !endpoint.isEmpty()) {
          new_list.push({ port, endpoint })
        }
      }
      return new_list
    },
  },
  watch: {
    current_serial_ports: {
      handler(new_ports: SerialEndpoint[]) {
        this.update_ports(new_ports)
      },
    },
  },
  mounted() {
    this.fetch_autopilot_serial_config_task.setAction(fetchAutopilotSerialConfiguration)
    this.fetch_serial_task.setAction(system_information.fetchSerial)
    this.update_ports(this.current_serial_ports)
  },
  methods: {
    update_ports(new_ports: SerialEndpoint[]) {
      for (const port of new_ports) {
        if (this.ports[port.port] === undefined) {
          this.ports[port.port] = port.endpoint ?? ''
        }
      }
    },
    async saveAndRestart(): Promise<void> {
      await back_axios({
        method: 'put',
        url: `${autopilot.API_URL}/serials`,
        timeout: 10000,
        data: this.new_data,
      })
        .catch((error) => {
          console.log(error)
          autopilot.setAutopilotSerialConfigurations([])
        })
      await this.restart_autopilot()
    },
    async restart_autopilot(): Promise<void> {
      await AutopilotManager.restart()
    },
    isValidEndpoint(input: string | undefined): (true | string) {
      if (!input || input.isEmpty()) {
        return true
      }
      let matches = 0
      for (const value of Object.values(this.ports)) {
        if (value === input) {
          matches += 1
          if (matches > 1) {
            return 'Duplicated entry!'
          }
        }
      }
      const regex1 = /(tcpclient|udp|tcpin|udpin):(?<ip>[^:]+):(?<port>\d+)$/
      if (regex1.test(input)) {
        const match = regex1.exec(input)
        const ip = match?.groups?.ip ?? ''
        const port = parseInt(match?.groups?.port ?? '-1', 10)
        if (!isIpAddress(ip)) {
          return 'IP is invalid'
        }
        if (port < 0 || port > 65535) {
          return 'port is invalid'
        }
        return true
      }
      const regex2 = /tcp:\d*:wait$/
      if (regex2.test(input)) {
        const match = regex2.exec(input)
        const port = parseInt(match?.[0] ?? '-1', 10)
        if (port < 0 || port > 65535) {
          return 'port is invalid'
        }
        return true
      }
      if (input.startsWith('/dev/')) {
        return true
      }
      return 'unknown format. Supported formats are "tcpclient", "udp", "tcpin", "udpin", and system device paths'
    },
  },
})
</script>
