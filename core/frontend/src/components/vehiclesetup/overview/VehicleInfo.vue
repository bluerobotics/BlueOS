<template>
  <v-card>
    <v-card-title class="align-center">
      Vehicle
    </v-card-title>
    <v-card-text>
      <v-simple-table dense>
        <tbody>
          <tr>
            <td><b>Flight Controller</b></td>
            <td>{{ boardType }}</td>
          </tr>
          <tr /><tr>
            <td><b>Firmware</b></td>
            <td>{{ firmware }}</td>
          </tr>
          <tr>
            <td><b>Onboard Computer</b></td>
            <td>{{ model }}</td>
          </tr>
          <tr>
            <td><b>Frame</b></td>
            <td>{{ frameType }}</td>
          </tr>
        </tbody>
      </v-simple-table>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import { fetchCurrentBoard, fetchFirmwareInfo } from '@/components/autopilot/AutopilotManagerUpdater'
import { OneMoreTime } from '@/one-more-time'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import system_information from '@/store/system-information'

export default Vue.extend({
  name: 'VehicleInfo',
  data() {
    return {
      fetch_firmware_info_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
      fetch_current_board_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
    }
  },
  computed: {
    frameType() {
      const param = autopilot_data.parameter('FRAME_CONFIG')
      const frame_class_param = autopilot_data.parameter('FRAME_CLASS')
      return param?.options?.[param?.value] ?? frame_class_param?.options?.[frame_class_param?.value] ?? null
    },
    boardType() {
      return autopilot.current_board?.name ?? null
    },
    firmware() {
      const { firmware_info } = autopilot
      return `${autopilot.firmware_vehicle_type}`
        + ` ${firmware_info?.version} (${firmware_info?.type.toLocaleLowerCase()})`
    },
    model() {
      return system_information.platform?.raspberry?.model ?? 'Unknown'
    },
  },
  mounted() {
    this.fetch_firmware_info_task.setAction(fetchCurrentBoard)
    this.fetch_current_board_task.setAction(fetchFirmwareInfo)
  },
})
</script>
