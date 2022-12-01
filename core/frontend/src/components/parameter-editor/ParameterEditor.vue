<template>
  <v-card
    elevation="0"
    class="mx-auto my-6"
  >
    <v-data-table
      v-if="finished_loading"
      :headers="[{ text: 'Name', value: 'name' },
                 { text: 'Description', value: 'description' },
                 { text: 'Value', value: 'value' }]"
      :items="params"
      item-key="name"
      class="elevation-1"
      :search="search"
      :custom-filter="filterOnlyCapsText"
      :sort-by="'name'"
      @click:row="editParam"
    >
      <template #top>
        <v-text-field
          v-model="search"
          label="Search"
          class="mx-4"
        />
      </template>
      <template #item.value="{ item }">
        {{ printParam(item) }}
      </template>
    </v-data-table>
    <div v-else>
      <spinning-logo size="30%" />
      <v-progress-linear
        :value="params_percentage"
        stream
        class="mt-5 mb-5"
        color="blue"
        height="20"
      >
        <template #default>
          <strong> Loading parameters: {{ params.length ?? 'loading' }} </strong>
        </template>
      </v-progress-linear>
    </div>
    <v-dialog
      v-model="edit_dialog"
      max-width="500px"
    >
      <v-card>
        <v-card-title>
          <span class="text-h5">{{ edited_param?.name ?? '' }}</span>
        </v-card-title>

        <v-card-text>
          <v-container
            v-if="edited_param"
          >
            <v-row v-if="edited_param.range">
              Max: {{ edited_param.range.high }}
              Min: {{ edited_param.range.low }}
            </v-row>
            <v-row v-if="edited_param.rebootRequired">
              Reboot Required
            </v-row>
            <v-row>
              {{ edited_param.description }}
            </v-row>
            <v-row>
              <v-col
                cols="6"
                sm="6"
                md="6"
              >
                <v-form
                  ref="form"
                >
                  <template v-if="!custom_input && edited_param.bitmask">
                    <v-checkbox
                      v-for="(key, value) in edited_param?.bitmask"
                      :key="value"
                      v-model="edited_bitmask"
                      dense
                      :label="key"
                      :value="2 ** value"
                    />
                  </template>
                  <v-select
                    v-else-if="!custom_input && edited_param?.options"
                    v-model.number="new_value"
                    :items="as_select_tems"
                    :rules="[() => true]"
                  />
                  <v-text-field
                    v-if="custom_input || (edited_param && !edited_param.options && !edited_param.bitmask)"
                    v-model.number="new_value"
                    label="Value"
                    type="number"
                    :step="edited_param.increment ?? 1"
                    :rules="forcing_input ? [] : [isInRange, isValidType]"
                  />

                  <v-checkbox
                    v-if="show_advanced_checkbox"
                    v-model="forcing_input"
                    dense
                    :label="'Force'"
                  />
                  <v-checkbox
                    v-if="show_custom_checkbox"
                    v-model="custom_input"
                    dense
                    :label="'Custom'"
                  />
                </v-form>
              </v-col>
            </v-row>
          </v-container>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn
            color="blue darken-1"
            text
            @click="edit_dialog = false"
          >
            Cancel
          </v-btn>
          <v-btn
            color="blue darken-1"
            text
            @click="saveParam(edited_param.rebootRequired)"
          >
            {{ edited_param?.rebootRequired ? "Save and Reboot" : "Save" }}
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter, { ParamType } from '@/types/autopilot/parameter'
import { parameters_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'

import SpinningLogo from '../common/SpinningLogo.vue'

const notifier = new Notifier(parameters_service)

export default Vue.extend({
  name: 'ParameterEditor',
  components: {
    SpinningLogo,
  },
  data() {
    return {
      search: '',
      edited_param: undefined as (undefined | Parameter),
      edit_dialog: false,
      edited_bitmask: [] as number[],
      forcing_input: false,
      custom_input: false,
      new_value: 0,
    }
  },
  computed: {
    params() {
      return autopilot_data.parameters
    },
    params_percentage() {
      return 100 * (autopilot_data.parameters.length / autopilot_data.parameters_total)
    },
    finished_loading() {
      return autopilot_data.finished_loading
    },
    form(): VForm {
      return this.$refs.form as VForm
    },
    show_advanced_checkbox(): boolean {
      return typeof this.isInRange(this.edited_param?.value ?? 0) === 'string'
    },
    show_custom_checkbox(): boolean {
      return !!(this.edited_param?.options || this.edited_param?.bitmask)
    },
    as_select_tems() {
      const entries = Object.entries(this.edited_param?.options ?? [])
      return entries.map(([value, name]) => ({ text: name, value: parseFloat(value), disabled: false }))
    },
  },
  methods: {
    isInRange(input: number): boolean | string {
      if (!this.edited_param?.range) {
        return true
      }
      if (input > this.edited_param.range.high) {
        return `Value should be smaller than ${this.edited_param.range.high}`
      }
      if (input < this.edited_param.range.low) {
        return `Value should be greater than ${this.edited_param.range.low}`
      }
      return true
    },
    isValidType(input: number): boolean | string {
      if (this.edited_param?.paramType.type.includes('UINT')) {
        if (input < 0) {
          return 'This parameter must be a positive Integer'
        }
      }
      if (this.edited_param?.paramType.type.includes('INT')) {
        if (!Number.isInteger(input)) {
          return 'This parameter must be an Integer'
        }
      }
      return true
    },
    editParam(param: Parameter) {
      if (param.readonly) {
        return
      }
      this.edited_param = param
      this.new_value = this.edited_param?.value ?? 0
      this.edit_dialog = true
      this.edited_bitmask = []
      if (param.bitmask === undefined) {
        return
      }
      // eslint-disable-next-line no-bitwise
      for (let v = 0; v < param.value; v += 1) {
        // eslint-disable-next-line no-bitwise
        const bitmask_value = 1 << v
        // eslint-disable-next-line no-bitwise
        if (bitmask_value & param.value) {
          this.edited_bitmask.push(bitmask_value)
        }
      }
    },
    async saveParam(reboot: boolean) {
      if (!this.forcing_input && !this.form?.validate()) {
        return
      }
      this.edit_dialog = false
      if (this.edited_param == null) {
        return
      }
      if (!this.custom_input && this.edited_param.bitmask !== undefined) {
        this.new_value = this.edited_bitmask.reduce((accumulator, current) => accumulator + current, 0)
      }
      let value = 0
      if (typeof this.new_value === 'string') {
        value = parseFloat(this.new_value)
      } else {
        value = this.new_value
      }
      const param_id = [...this.edited_param.name]
      while (param_id.length < 16) {
        param_id.push('\0')
      }
      mavlink2rest.sendMessage({
        header: {
          system_id: 255,
          component_id: 0,
          sequence: 0,
        },
        message: {
          type: 'PARAM_SET',
          param_value: value,
          target_system: 0,
          target_component: 0,
          param_id,
          param_type: {
            type: this.edited_param.paramType.type,
          },
        },
      })
      if (reboot) {
        await this.restart_autopilot()
        autopilot_data.reset()
      }
    },
    async restart_autopilot(): Promise<void> {
      autopilot.setRestarting(true)
      await back_axios({
        method: 'post',
        url: `${autopilot.API_URL}/restart`,
        timeout: 10000,
      })
        .catch((error) => {
          notifier.pushBackError('AUTOPILOT_RESTART_FAIL', error)
        })
        .finally(() => {
          autopilot.setRestarting(false)
        })
    },
    filterOnlyCapsText(value: string, search: string) {
      const re = new RegExp(search, 'i')
      return value != null
        && search != null
        && typeof value === 'string'
        && re.test(value)
    },
    printParam(param: Parameter): string {
      if ((param.bitmask || param.options === undefined) && param.value === 0) {
        return 'None'
      }

      if (param.options && param.value in param.options) {
        // TODO: fix this so it doesnt show text for values such as 2.5 (rounding down to 2)
        return param.options[param.value]
      }
      try {
        return param.value.toFixed(param.paramType.type.includes('INT') ? 0 : 2)
      } catch {
        return 'N/A'
      }
    },
  },
})
</script>

<style>
div.v-messages {
  min-height: 1px;
}
</style>
