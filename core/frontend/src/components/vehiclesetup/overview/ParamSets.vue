<template>
  <v-row class="main-container">
    <v-card
      v-if="settings.is_pirate_mode"
      class="card-container"
    >
      <v-card-title class="align-center">
        Reset Parameters to Firmware Defaults
      </v-card-title>
      <v-card-text>
        <p>
          This will effectively wipe your "eeprom". You will lose all your parameters, vehicle setup, and calibrations.
          Use this if you don't know which parameters you changed and need a clean start.
        </p>
      </v-card-text>
      <v-card-actions>
        <v-btn :disabled="wipe_successful" :loading="erasing" color="primary" @click="show_warning = true">
          Reset All Parameters
        </v-btn>
        <v-btn
          v-if="wipe_successful && !done"
          color="warning"
          :loading="rebooting"
          @click="restartAutopilot"
        >
          Reboot Autopilot
        </v-btn>
        <v-alert
          v-if="wipe_successful"
          dense
          text
          type="success"
        >
          Parameters reset <b>successful</b>. <span v-if="!done"> Please reboot the vehicle to apply changes. </span>
        </v-alert>
      </v-card-actions>
    </v-card>
    <v-card class="card-container">
      <v-card-title class="align-center">
        Load Recommended Parameter sets
      </v-card-title>
      <v-card-text>
        <p>
          These are the recommended parameter sets for your vehicle and firmware version. Curated by Blue Robotics
        </p>
      </v-card-text>
      <v-card-actions>
        <v-btn
          v-for="(paramSet, name) in filtered_param_sets"
          :key="name"
          color="primary"
          @click="loadParams(name, paramSet)"
        >
          {{ name.split('/').pop() }}
        </v-btn>
        <p v-if="(Object.keys(filtered_param_sets).length === 0)">
          No parameters available for this setup
        </p>
      </v-card-actions>
    </v-card>
    <ParameterLoader
      v-if="Object.keys(selected_paramset).length"
      :key="selected_paramset_name"
      :parameters="selected_paramset"
      @done="selected_paramset = {}"
    />

    <WarningDialog
      v-model="show_warning"
      :message="warningMessage"
      confirm-label="Yes, reset them"
      @confirm="wipe"
    />
  </v-row>
</template>

<script lang="ts">
import { SemVer } from 'semver'
import Vue from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import { fetchCurrentBoard } from '@/components/autopilot/AutopilotManagerUpdater'
import WarningDialog from '@/components/common/WarningDialog.vue'
import ParameterLoader from '@/components/parameter-editor/ParameterLoader.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import {
  MavCmd, MavResult,
} from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import Notifier from '@/libs/notifier'
import { fetchParamSets, paramSetsForFirmware } from '@/libs/parameter_repository'
import settings from '@/libs/settings'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Dictionary } from '@/types/common'
import { frontend_service } from '@/types/frontend_services'

const notifier = new Notifier(frontend_service)

export default Vue.extend({
  name: 'ParamSets',
  components: {
    ParameterLoader,
    WarningDialog,
  },
  data: () => ({
    all_param_sets: {} as Dictionary<Dictionary<number>>,
    selected_paramset: {} as Dictionary<number>,
    selected_paramset_name: undefined as (undefined | string),
    wipe_successful: false,
    rebooting: false,
    done: false,
    erasing: false,
    settings,
    show_warning: false,
  }),
  computed: {
    vehicle(): string | null {
      return autopilot.firmware_vehicle_type
    },
    version(): SemVer | null {
      return autopilot.firmware_info?.version ?? null
    },
    filtered_param_sets(): Dictionary<Dictionary<number>> {
      return paramSetsForFirmware(this.all_param_sets, this.vehicle, this.version, autopilot.current_board)
    },
    warningMessage(): string {
      return 'You will lose ALL your parameters, vehicle setup, and calibrations. Are you sure you want to reset?'
    },
  },
  mounted() {
    fetchCurrentBoard()
    this.loadParamSets()
  },
  methods: {
    async loadParamSets() {
      try {
        this.all_param_sets = await fetchParamSets()
      } catch (error) {
        notifier.pushError('PARAM_SETS_FETCH_FAIL', error)
      }
    },
    async loadParams(name: string, paramset: Dictionary<number>) {
      this.selected_paramset_name = name
      this.selected_paramset = { ...paramset }
    },
    async restartAutopilot(): Promise<void> {
      this.rebooting = true
      await AutopilotManager.restart()
      autopilot_data.reset()
      // reset to initial
      this.done = true
      this.rebooting = false
    },
    async wipe() {
      this.erasing = true
      mavlink2rest.sendCommandLong(
        MavCmd.MAV_CMD_PREFLIGHT_STORAGE,
        2, // PARAM_RESET_CONFIG_DEFAULT from MAV_CMD_PREFLIGHT_STORAGE
      )
      const timeout = 0
      try {
        const ack = await mavlink2rest.waitForAck(MavCmd.MAV_CMD_PREFLIGHT_STORAGE)
        if (ack.result.type !== MavResult.MAV_RESULT_ACCEPTED) {
          throw new Error(`Command not accepted: ${ack.result.type}`)
        }
        clearTimeout(timeout)
        this.wipe_successful = true
        autopilot_data.setRebootRequired(true)
      } catch (e) {
        this.wipe_successful = false
        notifier.pushError('PARAM_RESET_FAIL', `Parameters Reset failed: ${e}`, true)
      } finally {
        this.erasing = false
        this.show_warning = false
      }
    },

  },
})
</script>
<style scoped>
button {
    margin: 10px;
}

.main-container {
  display: flex;
  padding: 25px;
  gap: 10px;
}

.card-container {
  flex: 1 1 calc(50% - 10px);
  max-width: calc(50% - 0px);
  min-width: 600px;
}

.virtual-table-row {
  display: flex;
  margin: 0;
  margin-bottom: 15px;
  border-bottom: 1px solid #eee;
}

.virtual-table-cell {
  flex: 1;
  padding: 5px;
  height: 30px;
}
.virtual-table-cell .v-input {
  margin-top: -6px;
}

.checkbox-label label {
  font-weight: 700;
}
</style>
