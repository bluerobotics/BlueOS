<template>
  <v-dialog
    v-model="should_open"
    width="fit-content"
    max-width="80%"
    @click:outside="done"
  >
    <v-card>
      <v-card-title class="pt-6">
        Loading Parameters
      </v-card-title>
      <v-card-text v-if="Object.keys(different_param_set).length !== 0">
        <v-row class="virtual-table-row">
          <v-col class="virtual-table-cell checkbox-cell">
            <v-checkbox
              ref="selectAllCheckbox"
              v-model="select_all"
              class="virtual-table-cell"
              label="Write"
              :disabled="writing"
              :indeterminate="select_all === null"
              @click="toggleSelectAll"
            />
          </v-col>
          <v-col class="virtual-table-cell name-cell">
            <strong>Name</strong>
          </v-col>
          <v-col class="virtual-table-cell">
            <strong>Value</strong>
          </v-col>
          <v-col class="virtual-table-cell">
            <strong>New Value</strong>
          </v-col>
        </v-row>
        <!-- display all parameters in a concise table using virtual scroller -->
        <v-virtual-scroll
          :items="parametersFromSet(different_param_set)"
          height="300"
          item-height="30"
          class="virtual-table"
        >
          <template #default="{ item }">
            <v-row class="virtual-table-row">
              <v-col class="virtual-table-cell">
                <v-checkbox
                  v-model="param_checkboxes[item.name]"
                  class="checkbox-label checkbox-cell"
                  :disabled="writing"
                />
              </v-col>
              <v-col class="virtual-table-cell name-cell">
                <v-tooltip bottom>
                  <template #activator="{ on }">
                    <div :style="!item.current ? { color: 'var(--v-warning-base)' } : {}" v-on="on">
                      {{ item.name }}
                    </div>
                  </template>
                  <span>
                    {{
                      item.current
                        ? item.current?.description ?? 'No description provided'
                        : 'Parameter not found in Autopilot data, most likely will not be written to the vehicle.'
                    }}
                  </span>
                </v-tooltip>
              </v-col>
              <v-col class="virtual-table-cell">
                <v-tooltip :disabled="!item.current" bottom>
                  <template #activator="{ on }">
                    <div
                      class="large-text-cell"
                      v-on="on"
                    >
                      {{ item.current ? printParamWithUnit(item.current) : 'N/A' }}
                    </div>
                  </template>
                  <span>
                    {{ item.current ? printParamWithUnit(item.current) : 'N/A' }}
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
                      {{ item.current ? printParamWithUnit(item.new) : item.new.value }}
                    </div>
                  </template>
                  <span>
                    {{ item.current ? printParamWithUnit(item.new) : item.new.value }}
                  </span>
                </v-tooltip>
              </v-col>
            </v-row>
          </template>
        </v-virtual-scroll>
        <v-progress-linear
          v-if="user_selected_params_length > 0 && initial_size > 0"
          slot="progress"
          :color="error ? 'red' : 'blue'"
          height="20"
          :value="progress"
        >
          <template #default>
            <strong
              class="ml-5"
            >
              {{ user_selected_params_length }} to go
            </strong>
          </template>
        </v-progress-linear>
      </v-card-text>
      <v-card-text v-else-if="write_finished && initial_size > 0">
        <v-alert
          type="success"
        >
          Parameters written successfully
        </v-alert>
      </v-card-text>
      <v-card-text v-else>
        No parameters to change. This means all the
        parameters in this group are already set to the desired values
      </v-card-text>
      <v-card-text v-if="error">
        <v-alert
          type="error"
        >
          {{ error }}
        </v-alert>
      </v-card-text>
      <v-card-actions class="justify-center">
        <v-btn
          :disabled="user_selected_params_length === 0 || writing"
          class="ma-6 elevation-2"
          x-large
          color="primary"
          @click="writeParams"
        >
          Write Parameters
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'
import { Dictionary } from 'vue-router'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import { printParamWithUnit } from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'ParameterLoader',
  props: {
    parameters: {
      type: Object as PropType<Dictionary<number>> | undefined,
      default: undefined,
    },
  },
  data: () => ({
    initial_size: 0,
    param_checkboxes: {} as Dictionary<boolean>,
    select_all: true as boolean | null,
    retries: 0,
    retry_interval: 0,
    should_open: false,
    error: false as boolean | string,
    writing: false,
  }),
  computed: {
    progress(): number {
      return 100 - this.different_param_set_length / this.initial_size * 100
    },
    writeable_param_set(): Dictionary<number> {
      return this.filterParamsByReadOnly(this.parameters)
    },
    different_param_set(): Dictionary<number> {
      return this.filterParamsByValue(this.writeable_param_set)
    },
    user_selected_params(): Dictionary<number> {
      return this.filterParamsBySelection(this.different_param_set)
    },
    different_param_set_length(): number {
      return Object.keys(this.different_param_set).length
    },
    user_selected_params_length(): number {
      return Object.keys(this.user_selected_params).length
    },
    write_finished(): boolean {
      return this.user_selected_params_length === 0
    },
  },
  watch: {
    param_checkboxes: {
      deep: true,
      handler() {
        this.updateSelectAllStatus()
      },
    },
    parameters: {
      handler(newval) {
        if (Object.keys(this.writeable_param_set).length !== 0) {
          this.should_open = true
        }
        this.updateParamCheckboxes(newval)
      },
    },
  },
  methods: {
    done() {
      this.$emit('done')
      this.error = false
      this.retries = 0
      setTimeout(() => {
        // delay this as the dialog is still open when the done event is emitted
        // which causes the text to change during the close animation
        this.writing = false
      }, 500)
      this.initial_size = 0
      this.should_open = false
    },
    toggleSelectAll() {
      const new_value = this.select_all === null ? true : this.select_all
      for (const key of Object.keys(this.param_checkboxes)) {
        this.$set(this.param_checkboxes, key, new_value)
      }
    },
    writeParams() {
      this.writing = true
      this.initial_size = this.user_selected_params_length
      this.writeSelectedParams()
      this.retry_interval = setInterval(() => {
        if (this.user_selected_params_length) {
          this.retries += 1
          if (this.retries > 5) {
            clearInterval(this.retry_interval)
            this.retries = 0
            this.error = 'Failed to write some parameters. Please restart the vehicle and try again.'
            return
          }
          this.writeSelectedParams()
        } else {
          clearInterval(this.retry_interval)
        }
      }, 1000)
    },
    writeSelectedParams() {
      for (const [name, value] of Object.entries(this.user_selected_params)) {
        this.writeParam(name, value)
      }
    },
    writeParam(name: string, value: number) {
      mavlink2rest.setParam(name, value, autopilot_data.system_id)
    },
    filterParamsByReadOnly(params: Dictionary<number>): Dictionary<number> {
      return Object.fromEntries(
        Object.entries(params).filter(([name]) => {
          const param = autopilot_data.parameter(name)
          return !param?.readonly ?? true
        }),
      )
    },
    filterParamsByValue(params: Dictionary<number>): Dictionary<number> {
      return Object.fromEntries(
        Object.entries(params).filter(([name, value]) => {
          const param = autopilot_data.parameter(name)
          if (!param) {
            return true
          }
          return Math.abs(param.value - value) > 0.0001
        }),
      )
    },
    filterParamsBySelection(params: Dictionary<number>): Dictionary<number> {
      return Object.fromEntries(
        Object.entries(params).filter(([name]) => this.param_checkboxes[name]),
      )
    },
    updateSelectAllStatus() {
      const all_checked = Object.values(this.param_checkboxes).every((val) => val)
      const some_checked = Object.values(this.param_checkboxes).some((val) => val)
      // eslint-disable-next-line no-nested-ternary
      this.select_all = all_checked ? true : some_checked ? null : false
    },
    updateParamCheckboxes(params: Dictionary<number>) {
      for (const [name, _value] of Object.entries(params)) {
        this.$set(this.param_checkboxes, name, true)
      }
    },
    parametersFromSet(paramset: Dictionary<number>) {
      return Object.entries(paramset).map(([name, value]) => {
        const currentParameter = autopilot_data.parameter(name)

        return {
          name,
          current: currentParameter ?? undefined,
          new: { ...currentParameter, value },
        }
      })
    },
    printParamWithUnit,
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

.checkbox-label label {
  font-weight: 700;
}

.name-cell {
  min-width: 200px;
}

.checkbox-cell {
  width: 50px;
}

.virtual-table {
  overflow-x: hidden;
}
</style>
