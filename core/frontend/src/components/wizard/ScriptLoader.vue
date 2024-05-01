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
    <p v-else-if="has_script_load_error">
      Unable to load scripts.
    </p>
    <p v-else-if="invalid_board">
      Determining current board...
    </p>
    <p v-else-if="filtered_scripts?.length === 0">
      No scripts available for this setup.
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

export default Vue.extend({
  name: 'ScriptLoader',
  props: {
    vehicle: {
      type: String,
      required: true,
    },
    online: {
      type: Boolean,
      required: true,
    },
  },
  data: () => ({
    all_scripts: [] as string[],
    selected_scripts: [] as string[],
    version: undefined as (undefined | SemVer),
    is_loading_scripts: false,
    has_script_load_error: false,
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
    invalid_board(): boolean {
      return !this.board
    },
    is_loading(): boolean {
      return this.is_loading_scripts || this.invalid_board
    },
  },
  watch: {
    vehicle() {
      this.version = undefined
      this.setUpScripts()
    },
  },
  mounted() {
    callPeriodically(fetchCurrentBoard, 10000)
  },
  beforeDestroy() {
    stopCallingPeriodically(fetchCurrentBoard)
  },
  methods: {
    async setUpScripts() {
      if (!this.online && this.vehicle !== '') {
        setTimeout(() => this.setUpScripts(), 1000)
        return
      }

      this.is_loading_scripts = true
      this.has_script_load_error = false
      try {
        this.version = await this.fetchLatestFirmwareVersion()
        this.all_scripts = await this.fetchScripts()
      } catch (error) {
        this.has_script_load_error = true
      } finally {
        this.is_loading_scripts = false
      }
    },
    isNotEmpty(value: string): boolean {
      return value !== ''
    },
    async fetchScripts() {
      const response = await fetch(REPOSITORY_SCRIPTS_URL)
      const scripts = await response.json()

      return scripts
    },
    async fetchLatestFirmwareVersion(): Promise<SemVer | undefined> {
      const firmwares = await availableFirmwares(this.vehicle as Vehicle)
      const found: Firmware | undefined = firmwares.find((firmware) => firmware.name.includes('STABLE'))

      return found ? new SemVer(found.name.split('-')[1]) : undefined
    },
    setScriptsList(list: string[]) {
      this.selected_scripts = list
      this.$emit('input', list)
    },
  },
})
</script>
