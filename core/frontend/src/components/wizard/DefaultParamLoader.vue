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
    <p v-if="has_parameters_load_error">
      Failed to load parameters.
    </p>
    <p v-else-if="fetch_retries > 0">
      Failed to fetch parameters, trying again...
    </p>
    <p v-else-if="is_loading_parameters">
      Loading parameters...
    </p>
    <p v-else-if="invalid_board">
      Determining current board...
    </p>
    <p v-else-if="(Object.keys(filtered_param_sets).length === 0)">
      No parameters available for this setup.
    </p>
    <v-card
      v-if="Object.keys(value).length !== 0"
    >
      <v-card-text>
        <v-row class="virtual-table-row">
          <v-col class="virtual-table-cell name-cell">
            <strong>Name</strong>
          </v-col>
          <v-col class="virtual-table-cell">
            <strong>Value</strong>
          </v-col>
        </v-row>
      </v-card-text>
      <v-virtual-scroll
        :items="parametersFromSet(value)"
        height="250"
        item-height="30"
        class="virtual-table"
      >
        <template #default="{ item }">
          <v-row class="virtual-table-row">
            <v-col class="virtual-table-cell name-cell">
              <v-tooltip bottom>
                <template #activator="{ on }">
                  <div v-on="on">
                    {{ item.name }}
                  </div>
                </template>
                <span>
                  {{ item.current?.description ?? 'No description provided' }}
                </span>
              </v-tooltip>
            </v-col>
            <v-col class="virtual-table-cell">
              <v-tooltip bottom>
                <template #activator="{ on }">
                  <div
                    class="large-text-cell"
                    v-on="on"
                  >
                    {{ item.current ? printParamWithUnit(item.current) : item.value }}
                  </div>
                </template>
                <span>
                  {{ item.current ? printParamWithUnit(item.current) : item.value }}
                </span>
              </v-tooltip>
            </v-col>
          </v-row>
        </template>
      </v-virtual-scroll>
    </v-card>
  </div>
</template>

<script lang="ts">
import { SemVer } from 'semver'
import Vue, { PropType } from 'vue'
import { Dictionary } from 'vue-router'

import { OneMoreTime } from '@/one-more-time'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import { Firmware, Vehicle } from '@/types/autopilot'
import { printParamWithUnit } from '@/types/autopilot/parameter'
import { VForm } from '@/types/vuetify'

import { availableFirmwares, fetchCurrentBoard } from '../autopilot/AutopilotManagerUpdater'

const REPOSITORY_URL = 'https://docs.bluerobotics.com/Blueos-Parameter-Repository/params_v1.json'

const MAX_FETCH_PARAMS_RETRIES = 4

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
    selected_param_set: {},
    selected_param_set_name: '' as string,
    version: undefined as (undefined | SemVer),
    fetch_retries: 0,
    is_loading_parameters: false,
    has_parameters_load_error: false,
    fetch_current_board_task: new OneMoreTime({ delay: 10000, disposeWith: this }),
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
      return {
        ...fw_params,
        [this.not_load_default_params_option]: {},
      }
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
    invalid_board(): boolean {
      return !this.board
    },
    is_loading(): boolean {
      return (
        this.is_loading_parameters
        || this.invalid_board
        || this.fetch_retries > 0 && !this.has_parameters_load_error
      )
    },
    not_load_default_params_option(): string {
      return 'Do not load default parameters'
    },
  },
  watch: {
    vehicle() {
      this.selected_param_set = {}
      this.selected_param_set_name = ''
      this.fetch_retries = 0
      this.version = undefined

      this.setUpParams()
    },
  },
  mounted() {
    this.fetch_current_board_task.setAction(fetchCurrentBoard)
  },
  methods: {
    async setUpParams() {
      this.$emit('input', undefined)

      this.is_loading_parameters = true
      this.has_parameters_load_error = false
      try {
        this.version = await this.fetchLatestFirmwareVersion()
        this.all_param_sets = await this.fetchParamSets()

        this.fetch_retries = 0
      } catch (error) {
        this.fetch_retries += 1

        if (this.fetch_retries <= MAX_FETCH_PARAMS_RETRIES) {
          setTimeout(() => this.setUpParams(), 2500)
          return
        }

        this.has_parameters_load_error = true
      } finally {
        this.is_loading_parameters = false
      }

      this.$emit('input', {})
      this.selected_param_set_name = this.filtered_param_sets_names.length > 1
        ? ''
        : this.not_load_default_params_option
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
    parametersFromSet(paramset: Dictionary<number>) {
      return Object.entries(paramset).map(([name]) => {
        const currentParameter = autopilot_data.parameter(name)

        return {
          name,
          current: currentParameter,
          value: paramset[name],
        }
      })
    },
    printParamWithUnit,
  },
})
</script>
<style scoped>
.virtual-table-row {
  display: flex;
  margin: 0;
  margin-bottom: 15px;
  border-bottom: 1px solid #eee;
  flex-wrap: nowrap;
}

.virtual-table-cell {
  flex: 1;
  padding: 5px;
  height: 30px;
  min-width: 150px;
}
.virtual-table-cell .v-input {
  margin-top: -6px;
}
.virtual-table-cell .large-text-cell {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.name-cell {
  min-width: 200px;
}

.virtual-table {
  overflow-x: hidden;
}
</style>
