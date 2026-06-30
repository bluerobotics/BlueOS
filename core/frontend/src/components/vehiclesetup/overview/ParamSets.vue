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
      <v-card-actions class="flex-wrap">
        <p v-if="filtered_param_sets.length === 0">
          No parameters available for this setup
        </p>

        <v-btn
          v-for="item in current_param_sets"
          :key="item.name"
          color="primary"
          @click="loadParams(item.name, item.paramset)"
        >
          {{ displayName(item.name) }}
          <span class="version-tag ml-2">v{{ item.version_label }}</span>
        </v-btn>

        <p
          v-if="current_param_sets.length === 0 && outdated_param_sets.length > 0"
          class="ma-2 text--secondary full-row"
        >
          No parameter sets match your firmware version. Older sets are shown below.
        </p>

        <v-btn
          v-if="current_param_sets.length > 0 && outdated_param_sets.length > 0"
          text
          small
          @click="show_older = !show_older"
        >
          {{ show_older ? 'Hide' : 'Show' }}
          {{ outdated_param_sets.length }}
          older set{{ outdated_param_sets.length === 1 ? '' : 's' }}
        </v-btn>

        <template v-if="show_older || current_param_sets.length === 0">
          <v-tooltip
            v-for="item in outdated_param_sets"
            :key="item.name"
            bottom
          >
            <template #activator="{ on }">
              <v-btn
                color="warning"
                outlined
                @click="loadParams(item.name, item.paramset)"
                v-on="on"
              >
                <v-icon
                  left
                  small
                >
                  mdi-alert
                </v-icon>
                {{ displayName(item.name) }}
                <span class="version-tag ml-2">v{{ item.version_label }}</span>
              </v-btn>
            </template>
            <span>
              Outdated: built for firmware {{ item.version_label }}
              (current is {{ current_version_label }})
            </span>
          </v-tooltip>
        </template>
      </v-card-actions>
    </v-card>
    <ParameterLoader
      v-if="selected_paramset"
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
import settings from '@/libs/settings'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Dictionary } from '@/types/common'
import { frontend_service } from '@/types/frontend_services'

const notifier = new Notifier(frontend_service)
const REPOSITORY_URL = 'https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json'

interface FilteredParamSet {
  name: string
  paramset: Dictionary<number>
  version: SemVer
  version_label: string
  outdated: boolean
}

type Candidate = Omit<FilteredParamSet, 'outdated'> & { has_patch: boolean }

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

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
    show_older: false,
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
    filtered_param_sets(): FilteredParamSet[] {
      if (!this.vehicle || !this.board || !this.version) {
        return []
      }

      // Match keys shaped like ".../<vehicle>/<X.Y[.Z]>/<board>/..."
      // Trailing slash on the board avoids matching Navigator vs Navigator64, etc.
      const pattern = new RegExp(
        `/${escapeRegex(this.vehicle)}/(\\d+\\.\\d+(?:\\.\\d+)?)/${escapeRegex(this.board)}/`,
        'i',
      )

      const current = this.version
      const candidates: Candidate[] = []

      for (const [name, paramset] of Object.entries(this.all_param_sets)) {
        const match = name.match(pattern)
        if (!match) {
          continue
        }

        const version_label = match[1]
        const has_patch = version_label.split('.').length === 3
        let version: SemVer
        try {
          // Normalize "4.5" -> "4.5.0" so SemVer can parse it
          version = new SemVer(has_patch ? version_label : `${version_label}.0`)
        } catch {
          continue
        }

        // Skip paramsets targeting a newer firmware than the one currently installed
        if (version.compare(current) > 0) {
          continue
        }

        candidates.push({
          name, paramset, version, version_label, has_patch,
        })
      }

      // Specificity: 2 = exact patch match, 1 = same major.minor, 0 = older
      function specificity(c: Candidate): number {
        if (c.has_patch && c.version.compare(current) === 0) return 2
        if (c.version.major === current.major && c.version.minor === current.minor) return 1
        return 0
      }
      const scored = candidates.map((c) => ({ candidate: c, score: specificity(c) }))
      const best = scored.reduce((max, s) => Math.max(max, s.score), 0)

      const result: FilteredParamSet[] = scored.map(({ candidate, score }) => ({
        name: candidate.name,
        paramset: candidate.paramset,
        version: candidate.version,
        version_label: candidate.version_label,
        outdated: best === 0 || score < best,
      }))

      // Current paramsets first, then outdated ones sorted newest-first
      result.sort((a, b) => {
        if (a.outdated !== b.outdated) {
          return a.outdated ? 1 : -1
        }
        return b.version.compare(a.version)
      })

      return result
    },
    current_param_sets(): FilteredParamSet[] {
      return this.filtered_param_sets.filter((p) => !p.outdated)
    },
    outdated_param_sets(): FilteredParamSet[] {
      return this.filtered_param_sets.filter((p) => p.outdated)
    },
    current_version_label(): string {
      if (!this.version) return 'unknown'
      return `${this.version.major}.${this.version.minor}.${this.version.patch}`
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
      const response = await fetch(REPOSITORY_URL)
      const paramSets = await response.json()
      this.all_param_sets = paramSets
    },
    async loadParams(name: string, paramset: Dictionary<number>) {
      this.selected_paramset_name = name
      this.selected_paramset = paramset
    },
    displayName(name: string): string {
      const basename = name.split('/').pop() ?? name
      return basename.replace(/\.params$/i, '')
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

.version-tag {
  font-size: 0.75em;
  font-weight: normal;
  opacity: 0.7;
}

.full-row {
  flex-basis: 100%;
}
</style>
