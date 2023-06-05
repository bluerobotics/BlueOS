<template>
  <v-card class="ma-2 pa-2">
    <v-card-title class="align-center">
      Load Default Parameters
    </v-card-title>
    <v-card-text>
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
    </v-card-text>
    <parameterloader
      v-if="selected_paramset"
      :parameters="selected_paramset"
      @done="selected_paramset = {}"
    />
  </v-card>
</template>

<script lang="ts">
import { SemVer } from 'semver'
import Vue from 'vue'
import { Dictionary } from 'vue-router/types/router'

import parameterloader from '@/components/parameter-editor/ParameterLoader.vue'
import autopilot from '@/store/autopilot_manager'

const REPOSITORY_URL = 'https://williangalvani.github.io/Blueos-Parameter-Repository/params_v1.json'

export default Vue.extend({
  name: 'ParamSets',
  components: {
    parameterloader,
  },
  data: () => ({
    all_param_sets: {} as Dictionary<Dictionary<number>>,
    selected_paramset: {} as Dictionary<number>,
    selected_paramset_name: undefined as (undefined | string),
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
      // fetch json file from https://williangalvani.github.io/Blueos-Parameter-Repository/params.json
      // and parse it into a dictionary
      const response = await fetch(REPOSITORY_URL)
      const paramSets = await response.json()
      this.all_param_sets = paramSets
    },
    async loadParams(name: string, paramset: Dictionary<number>) {
      this.selected_paramset_name = name
      this.selected_paramset = paramset
    },
  },
})
</script>
<style scoped>
button {
    margin: 10px;
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
