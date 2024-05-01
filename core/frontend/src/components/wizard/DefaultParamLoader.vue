<template>
  <div class="d-flex flex-column align-center ma-5" style="width: 100%; height: 100%;">
    <v-form ref="select">
      <v-select
        v-model="selected_param_set_name"
        :items="[...filtered_param_sets_names, not_load_default_params_option]"
        item-text="sanitized"
        item-value="full"
        :label="`Parameter Sets (${board} - ${vehicle} - ${version})`"
        :loading="is_loading"
        :disabled="is_loading_parameters"
        style="min-width: 330px;"
        :rules="[isNotEmpty]"
        @change="setParamSet(filtered_param_sets[selected_param_set_name])"
      />
    </v-form>
    <p v-if="is_loading_parameters">
      Loading parameters...
    </p>
    <p v-else-if="has_parameters_load_error">
      Unable to load parameters.
    </p>
    <p v-else-if="invalid_board">
      Determining current board...
    </p>
    <p v-else-if="(Object.keys(filtered_param_sets).length === 0)">
      No parameters available for this setup.
    </p>
    <v-virtual-scroll
      v-if="value_items.length > 0"
      class="flex-grow"
      :items="value_items"
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
import { Dictionary } from 'vue-router'

import autopilot from '@/store/autopilot_manager'
import { Firmware, Vehicle } from '@/types/autopilot'
import { VForm } from '@/types/vuetify'
import { callPeriodically, stopCallingPeriodically } from '@/utils/helper_functions'

import { availableFirmwares, fetchCurrentBoard } from '../autopilot/AutopilotManagerUpdater'

const REPOSITORY_URL = 'https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json'

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
    online: {
      type: Boolean,
      required: true,
    },
  },
  data: () => ({
    all_param_sets: {} as Dictionary<Dictionary<number>>,
    selected_param_set: {},
    selected_param_set_name: '' as string,
    version: undefined as (undefined | SemVer),
    is_loading_parameters: false,
    has_parameters_load_error: false,
  }),
  computed: {
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
      return fw_params
    },
    filtered_param_sets_names(): {full: string, sanitized: string}[] {
      return Object.keys(this.filtered_param_sets ?? {}).map((full) => ({
        full,
        // e.g. "ArduSub/BlueROV2/4.0.3/BlueROV2.params" -> "BlueROV2"
        sanitized: full.split('/').pop()?.split('.')[0] || '',
      }))
    },
    board(): string | undefined {
      return autopilot.current_board?.name
    },
    value_items(): { key: string, value: number }[] {
      return Object.entries(this.value ?? {}).map(([key, value]) => ({ key, value }))
    },
    invalid_board(): boolean {
      return !this.board
    },
    is_loading(): boolean {
      return this.is_loading_parameters || this.invalid_board
    },
    not_load_default_params_option(): string {
      return 'Do not load default parameters'
    },
  },
  watch: {
    vehicle() {
      this.version = undefined
      this.setUpParams()
    },
  },
  mounted() {
    callPeriodically(fetchCurrentBoard, 10000)
  },
  beforeDestroy() {
    stopCallingPeriodically(fetchCurrentBoard)
  },
  methods: {
    async setUpParams() {
      if (!this.online && this.vehicle !== '') {
        setTimeout(() => this.setUpParams(), 1000)
        return
      }

      this.is_loading_parameters = true
      this.has_parameters_load_error = false
      try {
        this.version = await this.fetchLatestFirmwareVersion()
        this.all_param_sets = await this.fetchParamSets()
      } catch (error) {
        this.has_parameters_load_error = true
      } finally {
        this.is_loading_parameters = false

        this.selected_param_set_name = this.filtered_param_sets_names.length > 0
          ? ''
          : this.not_load_default_params_option
      }
    },
    // this is used by Wizard.vue, but eslint doesn't detect it
    // eslint-disable-next-line
    validateParams(): boolean {
      const element = this.$refs.select as VForm
      return element.validate()
    },
    isNotEmpty(value: string): boolean {
      return value !== ''
    },
    async fetchParamSets() {
      const response = await fetch(REPOSITORY_URL)
      const parameters = await response.json()

      return parameters
    },
    async fetchLatestFirmwareVersion(): Promise<SemVer | undefined> {
      const firmwares = await availableFirmwares(this.vehicle as Vehicle)
      const found: Firmware | undefined = firmwares.find((firmware) => firmware.name.includes('STABLE'))

      return found ? new SemVer(found.name.split('-')[1]) : undefined
    },
    setParamSet(paramSet: Dictionary<number>) {
      this.selected_param_set = paramSet
      this.$emit('input', paramSet)
    },
  },
})
</script>
