<template>
  <div class="d-flex flex-column align-center ma-5" style="width: 100%; height: 100%;">
    <v-form>
      <v-select
        v-model="selected_scripts"
        clearable
        multiple
        chips
        persistent-hint
        :items="[...filtered_scripts]"
        item-text="sanitized"
        item-value="full"
        :label="`Scripts for (${board} - ${vehicle} - ${version})`"
        :loading="is_loading"
        :disabled="is_loading_scripts"
        style="min-width: 330px;"
        :rules="[isNotEmpty]"
        @change="setScriptsList(selected_scripts)"
      />
    </v-form>
    <p v-if="is_loading_scripts">
      Loading scripts...
    </p>
    <p v-else-if="has_error">
      Unable to load scripts.
    </p>
    <p v-else-if="(!loading_timeout_reached && invalid_board_or_version)">
      Determining current board and firmware version...
    </p>
    <p v-else-if="(loading_timeout_reached && invalid_board_or_version)">
      Unable to determine current board or firmware version.
    </p>
    <p v-else-if="filtered_scripts?.length === 0">
      No scripts available for this setup
    </p>
  </div>
</template>

<script lang="ts">
import { SemVer } from 'semver'
import Vue from 'vue'

import autopilot from '@/store/autopilot_manager'
import { Firmware, Vehicle } from '@/types/autopilot'
import { callPeriodically, stopCallingPeriodically } from '@/utils/helper_functions'

import { availableFirmwares, fetchCurrentBoard } from '../autopilot/AutopilotManagerUpdater'

const REPOSITORY_ROOT = 'https://docs.bluerobotics.com/Blueos-Parameter-Repository'
const REPOSITORY_SCRIPTS_URL = `${REPOSITORY_ROOT}/scripts_v1.json`

const MAX_LOADING_TIME_MS = 25000

export default Vue.extend({
  name: 'ScriptLoader',
  props: {
    vehicle: {
      type: String,
      required: true,
    },
  },
  data: () => ({
    all_scripts: [] as string[],
    version: undefined as (undefined | SemVer),
    selected_scripts: [] as string[],
    is_loading_scripts: true,
    loading_timeout_reached: false,
    has_error: false,
  }),
  computed: {
    filtered_scripts(): string[] | undefined {
      // for scripts, we only check major version for now
      // TODO: support other vehicles
      let match_string: string
      if (this.vehicle === 'Rover') {
        match_string = `ArduRover/${this.version?.major}.`
      } else {
        return []
      }
      console.log(match_string)
      return this.all_scripts.filter((name) => name.includes(match_string)).map(
        (name) => name.replace('scripts/ardupilot/', ''),
      )
    },

    board(): string | undefined {
      return autopilot.current_board?.name
    },
    invalid_board_or_version(): boolean {
      return !this.board || !this.version
    },
    is_loading(): boolean {
      return (this.is_loading_scripts || this.invalid_board_or_version) && !this.loading_timeout_reached
    },
  },

  watch: {
    vehicle() {
      this.updateLatestFirmwareVersion().then((version: string) => {
        this.version = new SemVer(version.split('-')[1])
      })
    },
  },
  mounted() {
    callPeriodically(fetchCurrentBoard, 10000)
    this.updateLatestFirmwareVersion().then((version: string) => {
      this.version = new SemVer(version.split('-')[1])
    })
    this.fetchScripts()
    setTimeout(() => { this.onLoadingTimeout() }, MAX_LOADING_TIME_MS)
  },
  beforeDestroy() {
    stopCallingPeriodically(fetchCurrentBoard)
  },
  methods: {
    isNotEmpty(value: string): boolean {
      return value !== ''
    },
    async fetchScripts() {
      const response = await fetch(REPOSITORY_SCRIPTS_URL)
      const scripts = await response.json()
      this.all_scripts = scripts
      this.is_loading_scripts = false
    },
    updateLatestFirmwareVersion() {
      return availableFirmwares(this.vehicle as Vehicle)
        .then((firmwares: Firmware[]) => {
          const found: Firmware | undefined = firmwares.find((firmware) => firmware.name.includes('STABLE'))
          if (found === undefined) {
            return `Failed to find a stable version for vehicle (${this.vehicle})`
          }
          return found.name
        })
    },
    setScriptsList(list: string[]) {
      this.selected_scripts = list
      this.$emit('input', list)
    },
    onLoadingTimeout() {
      if (this.is_loading) {
        this.loading_timeout_reached = true

        if (!this.selected_scripts) {
          this.selected_scripts = []
        }
      }
    },
  },
})
</script>
