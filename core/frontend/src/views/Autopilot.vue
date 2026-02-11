<template>
  <v-card
    elevation="0"
    class="mx-auto my-12 px-1 py-6 text-center"
    min-width="370"
    max-width="720"
  >
    <v-card>
      <v-card-title>Autopilot</v-card-title>

      <v-tooltip bottom>
        <template #activator="{ on, attrs }">
          <v-btn
            icon
            class="wizard-btn"
            v-bind="attrs"
            v-on="on"
            @click="enable_wizard"
          >
            <v-icon>mdi-wizard-hat</v-icon>
          </v-btn>
        </template>
        <span>Click to activate wizard</span>
      </v-tooltip>

      <img height="80" :src="banner" />

      <v-card-text>
        <span v-if="board_undefined">No board running</span>
        <div v-else>
          <v-row
            v-for="(value, name) in autopilot_info"
            :key="name"
            class="ma-0"
            no-gutters
          >
            <v-col class="text-right ma-0 font-weight-bold">
              {{ name }}:
            </v-col>
            <v-col class="text-left ml-1">
              {{ value }}
            </v-col>
          </v-row>
          <br>
        </div>
        <not-safe-overlay />
        <v-expansion-panels v-if="is_external_board">
          <v-expansion-panel>
            <v-expansion-panel-header>
              Master endpoint
            </v-expansion-panel-header>
            <v-expansion-panel-content>
              <master-endpoint-manager />
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
        <v-expansion-panels v-else>
          <v-expansion-panel>
            <v-expansion-panel-header>
              Firmware update
            </v-expansion-panel-header>
            <v-expansion-panel-content>
              <firmware-manager />
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
        <v-expansion-panels v-if="settings.is_pirate_mode && isLinuxFlightController">
          <v-expansion-panel>
            <v-expansion-panel-header>
              Serial Port Configuration
            </v-expansion-panel-header>
            <v-expansion-panel-content>
              <autopilot-serial-configuration />
            </v-expansion-panel-content>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card-text>
      <v-card-actions class="d-flex justify-end align-center flex-wrap">
        <v-spacer />
        <v-btn
          v-if="settings.is_pirate_mode"
          color="secondary"
          :block="$vuetify.breakpoint.xs"
          class="ma-1"
          :disabled="restarting || !is_safe"
          @click="openBoardChangeDialog"
        >
          Change board
        </v-btn>
        <v-btn
          v-if="settings.is_pirate_mode"
          class="ma-1"
          :block="$vuetify.breakpoint.xs"
          color="secondary"
          :disabled="restarting"
          @click="start_autopilot"
        >
          Start autopilot
        </v-btn>
        <v-btn
          v-if="settings.is_pirate_mode"
          class="ma-1"
          :block="$vuetify.breakpoint.xs"
          color="secondary"
          :disabled="restarting"
          @click="stop_autopilot"
        >
          Stop autopilot
        </v-btn>
        <v-btn
          v-if="settings.is_pirate_mode && board_supports_restart"
          color="primary"
          class="ma-1"
          :block="$vuetify.breakpoint.xs"
          :disabled="restarting"
          @click="restart_autopilot"
        >
          Restart autopilot
        </v-btn>
      </v-card-actions>
    </v-card>
    <board-change-dialog
      v-model="show_board_change_dialog"
    />
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import ArduPilotBanner from '@/assets/img/banners/ArduPilot.svg'
import OpenPilotBanner from '@/assets/img/banners/OpenPilot.svg'
import PX4Banner from '@/assets/img/banners/PX4.svg'
import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import {
  fetchAvailableBoards, fetchCurrentBoard, fetchFirmwareInfo, fetchFirmwareVehicleType, fetchVehicleType,
} from '@/components/autopilot/AutopilotManagerUpdater'
import AutopilotSerialConfiguration from '@/components/autopilot/AutopilotSerialConfiguration.vue'
import BoardChangeDialog from '@/components/autopilot/BoardChangeDialog.vue'
import FirmwareManager from '@/components/autopilot/FirmwareManager.vue'
import MasterEndpointManager from '@/components/autopilot/MasterEndpointManager.vue'
import NotSafeOverlay from '@/components/common/NotSafeOverlay.vue'
import { MavAutopilot } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import Notifier from '@/libs/notifier'
import settings from '@/libs/settings'
import { OneMoreTime } from '@/one-more-time'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import bag from '@/store/bag'
import { FirmwareInfo, FlightController } from '@/types/autopilot'
import { autopilot_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const notifier = new Notifier(autopilot_service)

export default Vue.extend({
  name: 'Autopilot',
  components: {
    BoardChangeDialog,
    FirmwareManager,
    AutopilotSerialConfiguration,
    NotSafeOverlay,
    MasterEndpointManager,
  },
  data() {
    return {
      settings,
      show_board_change_dialog: false,
      fetch_available_boards_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_current_board_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_firmware_info_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_vehicle_type_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
      fetch_firmware_vehicle_type_task: new OneMoreTime({ delay: 5000, disposeWith: this }),
    }
  },
  computed: {
    board_supports_restart(): boolean {
      // this is a mavlink command, all boards should support it
      return true
    },
    autopilot_info(): Record<string, string> {
      let version = 'Unknown'
      if (this.firmware_info) {
        version = `${this.firmware_info.version} (${this.firmware_info.type})`
      }

      const record: Record<string, string> = {
        'Board name': this.current_board?.name ?? 'Unknown',
        Manufacturer: this.current_board?.manufacturer ?? 'Unknown',
        'Mavlink platform': this.current_board?.platform ?? 'Unknown',
        'Firmware version': version,
        'Vehicle type': `${this.vehicle_type ?? 'Unknown'} (${this.firmware_vehicle_type ?? 'Unknown'})`,
      }

      if (this.current_board?.path) {
        record.Path = this.current_board.path
      }

      return record
    },
    banner(): string {
      switch (autopilot_data.autopilot_type) {
        case MavAutopilot.MAV_AUTOPILOT_ARDUPILOTMEGA:
          return ArduPilotBanner
        case MavAutopilot.MAV_AUTOPILOT_OPENPILOT:
          return OpenPilotBanner
        case MavAutopilot.MAV_AUTOPILOT_PX4:
          return PX4Banner
        default:
          return undefined
      }
    },
    isLinuxFlightController(): boolean {
      // this is setup this way so we can include other linux boards in the list in the future
      const boardname = this.current_board?.name
      if (!boardname) {
        return false
      }
      return ['Navigator', 'Navigator64', 'SITL'].includes(boardname)
    },
    is_external_board(): boolean {
      return autopilot.current_board?.name === 'Manual'
    },
    current_board(): FlightController | null {
      return autopilot.current_board
    },
    firmware_info(): FirmwareInfo | null {
      return autopilot.firmware_info
    },
    firmware_vehicle_type(): string | null {
      return autopilot.firmware_vehicle_type
    },
    vehicle_type(): string | null {
      return autopilot.vehicle_type
    },
    board_undefined(): boolean {
      return this.current_board === null
    },
    restarting(): boolean {
      return autopilot.restarting
    },
    is_safe(): boolean {
      return autopilot_data.is_safe
    },
  },
  mounted() {
    this.fetch_available_boards_task.setAction(fetchAvailableBoards)
    this.fetch_current_board_task.setAction(fetchCurrentBoard)
    this.fetch_firmware_info_task.setAction(fetchFirmwareInfo)
    this.fetch_vehicle_type_task.setAction(fetchVehicleType)
    this.fetch_firmware_vehicle_type_task.setAction(fetchFirmwareVehicleType)
  },
  methods: {
    async enable_wizard(): Promise<void> {
      const payload = { version: 0 }
      await bag.setData('wizard', payload)
        .then((result) => {
          if (result) {
            this.$router.push('/')
            window.location.reload()
          }
        })
        .catch(() => {
          notifier.pushBackError('ENABLE_WIZARD', 'Failed to enable wizard')
        })
    },
    async start_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/start`,
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_START_FAIL', error)
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    async stop_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/stop`,
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_STOP_FAIL', error)
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    async restart_autopilot(): Promise<void> {
      await AutopilotManager.restart()
    },
    openBoardChangeDialog(): void {
      this.show_board_change_dialog = true
    },
  },
})
</script>

<style scoped>
.wizard-btn {
  position: absolute;
  right: 15px;
  top: 0;
}
</style>
