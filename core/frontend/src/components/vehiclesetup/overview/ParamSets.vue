<template>
  <v-row class="main-container">
    <v-card class="card-container">
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
        <v-btn :disabled="wipe_successful" :loading="erasing" color="primary" @click="wipe">
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
      <ParameterLoader
        v-if="selected_paramset"
        :parameters="selected_paramset"
        @done="selected_paramset = {}"
      />
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
        <ParameterLoader
          v-if="selected_paramset"
          :parameters="selected_paramset"
          @done="selected_paramset = {}"
        />
      </v-card-actions>
    </v-card>
  </v-row>
</template>

<script lang="ts">
import { SemVer } from 'semver'
import Vue from 'vue'

import * as AutopilotManager from '@/components/autopilot/AutopilotManagerUpdater'
import ParameterLoader from '@/components/parameter-editor/ParameterLoader.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import {
  MavCmd, MavResult,
} from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest-enum'
import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Dictionary } from '@/types/common'
import { frontend_service } from '@/types/frontend_services'

const notifier = new Notifier(frontend_service)
const REPOSITORY_URL = 'https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json'

export default Vue.extend({
  name: 'ParamSets',
  components: {
    ParameterLoader,
  },
  data: () => ({
    all_param_sets: {} as Dictionary<Dictionary<number>>,
    selected_paramset: {} as Dictionary<number>,
    selected_paramset_name: undefined as (undefined | string),
    wipe_successful: false,
    rebooting: false,
    done: false,
    erasing: false,
  }),
  computed: {
    board(): string | undefined {
      return autopilot.current_board?.name
    },
    vehicle(): string | null {
      return autopilot.firmware_vehicle_type
    },
    version(): SemVer | undefined {
      return autopilot.firmware_info?.version
    },
    filtered_param_sets(): Dictionary<Dictionary<number>> | undefined {
      const fw_patch = `${this.vehicle}/${this.version}/${this.board}`
      const fw_minor = `${this.vehicle}/${this.version?.major}.${this.version?.minor}/${this.board}`
      const fw_major = `${this.vehicle}/${this.version?.major}/${this.board}`

      // returns a new dict where the keys start with the fullname
      // e.g. "ArduSub/BlueROV2/4.0.3" -> "ArduSub/BlueROV2/4.0.3/BlueROV2"

      let fw_params = {}
      // try to find a paramset that matches the firmware version, starting from patch and walking up to major
      for (const string of [fw_patch, fw_minor, fw_major]) {
        fw_params = Object.fromEntries(
          Object.entries(this.all_param_sets).filter(
            ([name]) => name.toLocaleLowerCase().includes(string.toLowerCase()),
          ),
        )
        if (Object.keys(fw_params).length > 0) {
          break
        }
      }
      return {
        ...fw_params,
      }
    },
  },
  mounted() {
    this.loadParamSets()
  },
  methods: {
    async loadParamSets() {
      const response = await fetch(REPOSITORY_URL)
      const paramSets = await response.json()
      this.all_param_sets = paramSets
    },
    async loadParams(name: string, paramset: Dictionary<number>) {
      this.selected_paramset_name = name
      this.selected_paramset = paramset
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
