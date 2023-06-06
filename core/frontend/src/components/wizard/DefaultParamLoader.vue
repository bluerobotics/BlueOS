<template>
  <div class="d-flex flex-column align-center ma-5" style="width: 100%; height: 100%;">
    <v-select
      v-model="selectedParamSetName"
      :items="filtered_param_sets_names"
      item-text="sanitized"
      item-value="full"
      :loading="is_loading"
      :label="parameters_label"
      :disabled="isLoading || hasError || !version"
      style="min-width: 70%;"
      @change="setParamSet(filtered_param_sets[selectedParamSetName])"
    />
    <v-virtual-scroll
      v-if="valueItems.length > 0"
      class="flex-grow"
      :items="valueItems"
      height="200"
      item-height="20"
      style="min-width: 50%;"
    >
      <template #default="{ item }">
        <v-list-item>
          <v-list-item-content>
            <v-list-item-title>{{ item.key }} {{ item.value }}</v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </template>
    </v-virtual-scroll>
  </div>
</template>

<script lang="ts">
import { SemVer } from 'semver'
import Vue, { PropType } from 'vue'
import { Dictionary } from 'vue-router/types/router'

import autopilot from '@/store/autopilot_manager'
import { Firmware, Vehicle } from '@/types/autopilot'
import { callPeriodically, stopCallingPeriodically } from '@/utils/helper_functions'

import { availableFirmwares, fetchCurrentBoard } from '../autopilot/AutopilotManagerUpdater'

const REPOSITORY_URL = 'https://williangalvani.github.io/Blueos-Parameter-Repository/params_v1.json'

export default Vue.extend({
  name: 'DefaultParamLoader',
  props: {
    value: {
      type: Object as PropType<Dictionary<number>>,
      default: () => ({}),
    },
    vehicle: {
      type: String,
      required: true,
    },
  },
  data: () => ({
    all_param_sets: {} as Dictionary<Dictionary<number>>,
    version: undefined as (undefined | SemVer),
    selectedParamSet: {},
    selectedParamSetName: '' as string,
    isLoading: true,
    hasError: false,
    fetching_error: undefined as (undefined | string),
  }),
  computed: {
    parameters_label(): string {
      if (this.isLoading) {
        return 'Loading...'
      }
      if (this.fetching_error) {
        return 'Unable to fetch Firmware version'
      }
      return `Parameter Sets (${this.board} - ${this.vehicle} - ${this.version || '...'})`
    },
    is_loading() {
      return this.isLoading || this.hasError
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
        'No default parameters': {}, // Always include the "No default parameters" option
      }
    },
    filtered_param_sets_names(): {full: string, sanitized: string}[] {
      return Object.keys(this.filtered_param_sets ?? {}).map((full) => ({
        full,
        sanitized: full.split('/').pop()?.split('.')[0] || '',
      }))
    },
    board(): string | undefined {
      return autopilot.current_board?.name
    },
    valueItems(): { key: string, value: number }[] {
      return Object.entries(this.value ?? {}).map(([key, value]) => ({ key, value }))
    },
  },

  watch: {
    vehicle() {
      this.version = undefined
      this.fetching_error = undefined
      this.updateLatestFirmwareVersion().then((version: string) => {
        this.version = new SemVer(version.split('-')[1])
      })
    },
  },
  mounted() {
    this.loadParamSets().catch(() => {
      this.hasError = true
    }).finally(() => {
      this.isLoading = false
    })
    callPeriodically(fetchCurrentBoard, 10000)
    this.updateLatestFirmwareVersion().then((version: string) => {
      this.version = new SemVer(version.split('-')[1])
    })
  },
  beforeDestroy() {
    stopCallingPeriodically(fetchCurrentBoard)
  },
  methods: {
    updateLatestFirmwareVersion() {
      return availableFirmwares(this.vehicle as Vehicle)
        .then((firmwares: Firmware[]) => {
          const found: Firmware | undefined = firmwares.find((firmware) => firmware.name.includes('STABLE'))
          if (found === undefined) {
            return `Failed to find a stable version for vehicle (${this.vehicle})`
          }
          return found.name
        }).catch((error) => {
          this.fetching_error = error
          return 'unable to detect latest firmware version'
        })
    },
    setParamSet(paramSet: Dictionary<number>) {
      this.selectedParamSet = paramSet
      this.$emit('input', paramSet)
    },
    async loadParamSets() {
      try {
        // fetch json file from https://williangalvani.github.io/Blueos-Parameter-Repository/params.json
        // and parse it into a dictionary
        const response = await fetch(REPOSITORY_URL)
        const paramSets = await response.json()
        this.all_param_sets = paramSets
      } catch (error) {
        this.hasError = true
        throw error
      }
    },
  },
})
</script>
