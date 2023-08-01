<template>
  <v-dialog
    max-width="500px"
    :value="show"
    @input="showDialog"
  >
    <v-card>
      <v-card-title>
        <span class="text-h5">{{ param?.name ?? "" }}</span>
      </v-card-title>

      <v-card-text>
        <v-container v-if="param">
          <v-row v-if="param.rebootRequired">
            Reboot Required
          </v-row>
          <v-row>
            {{ param.description }}
          </v-row>
          <v-row
            v-if="param.range"
            class="pt-6"
          >
            Min: {{ param.range.low }} Max:
            {{ param.range.high }} Increment:
            {{ param.increment ?? 0.01 }}
          </v-row>
          <v-row>
            <v-col
              cols="6"
              sm="6"
              md="6"
            >
              <v-form
                ref="form"
                @submit.prevent="saveEditedParam(false)"
              >
                <template v-if="!custom_input && param.bitmask">
                  <v-checkbox
                    v-for="(key, value) in param?.bitmask"
                    :key="value"
                    v-model="selected_bitflags"
                    dense
                    :label="key"
                    :value="2 ** value"
                  />
                </template>
                <v-autocomplete
                  v-else-if="!custom_input && Object.entries(param?.options ?? []).length > 10"
                  v-model.number="new_value"
                  :items="as_select_tems"
                  variant="solo"
                />
                <v-select
                  v-else-if="!custom_input && param?.options"
                  v-model.number="new_value"
                  :items="as_select_tems"
                  :rules="[() => true]"
                />
                <v-text-field
                  v-if="
                    custom_input
                      || (param
                        && !param.options
                        && !param.bitmask
                      )
                  "
                  v-model.number="new_value"
                  label="Value"
                  type="number"
                  :step="param.increment ?? 0.01"
                  :suffix="param.units"
                  :rules="forcing_input ? [] : [isInRange, isValidType]"
                  @blur="updateVariables"
                  @keyup="isFormValid()"
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
          color="primary"
          @click="showDialog(false)"
        >
          Cancel
        </v-btn>
        <v-btn
          :disabled="param_value_not_changed || !forcing_input || !isValidType(new_value)"
          color="primary"
          @click="saveEditedParam()"
        >
          Save
        </v-btn>
        <v-btn
          v-if="param?.rebootRequired === true"
          v-tooltip="'Reboot required for parameter to take effect'"
          :disabled="param_value_not_changed || !forcing_input || !isValidType(new_value)"
          color="warning"
          @click="saveEditedParam(true)"
        >
          Save and Reboot
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script lang="ts">
import Vue, { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import Notifier from '@/libs/notifier'
import autopilot_data from '@/store/autopilot'
import autopilot from '@/store/autopilot_manager'
import Parameter from '@/types/autopilot/parameter'
import { parameters_service } from '@/types/frontend_services'
import { VForm } from '@/types/vuetify'
import back_axios from '@/utils/api'

const notifier = new Notifier(parameters_service)

export default Vue.extend({
  name: 'ParameterEditorDialog',
  model: {
    prop: 'show',
    event: 'change',
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    param: {
      type: Object as PropType<Parameter> | undefined,
      default: undefined,
    },
  },
  data() {
    return {
      custom_input: false,
      forcing_input: false,
      // Form can't be computed correctly, so we save it's state under data
      is_form_valid: false,
      new_value: 0,
      selected_bitflags: [] as number[],
    }
  },
  computed: {
    as_select_tems() {
      const entries = Object.entries(this.param?.options ?? [])
      return entries.map(([value, name]) => ({ text: name, value: parseFloat(value), disabled: false }))
    },
    edited_bitmask_value(): number {
      return this.selected_bitflags.reduce((accumulator, current) => accumulator + current, 0)
    },
    param_value_not_changed(): boolean {
      // Check if value is different
      return this.new_value === this.param?.value
        // Check if bitmask value, if valid, is different from current value
        && (this.param?.bitmask === undefined || this.edited_bitmask_value === this.param?.value)
    },
    show_advanced_checkbox(): boolean {
      return typeof this.isInRange(this.new_value ?? 0) === 'string'
    },
    show_custom_checkbox(): boolean {
      return !!(this.param?.options || this.param?.bitmask)
    },
  },
  watch: {
    new_value(): void {
      this.updateSelectedFlags()
      this.isFormValid()
    },
    forcing_input(): void {
      this.isFormValid()
    },
    edited_bitmask_value(): void {
      this.new_value = this.edited_bitmask_value
    },
    show(): void {
      this.new_value = this.param.value

      if (!this.show) {
        return
      }

      this.updateVariablesAtStart()
    },
  },
  methods: {
    isFormValid(): boolean {
      const form = this.$refs.form as VForm
      this.is_form_valid = form?.validate() === true
      return this.is_form_valid
    },
    isInRange(input: number | string): boolean | string {
      // The input value is an empty string when the field is empty
      if (typeof input === 'string' && input?.trim().length === 0) {
        return 'This should be a number between min and max'
      }

      if (!this.param?.range) {
        return true
      }
      if (input > this.param.range.high) {
        return `Value should be smaller than ${this.param.range.high}`
      }
      if (input < this.param.range.low) {
        return `Value should be greater than ${this.param.range.low}`
      }
      return true
    },
    isValidType(input: number): boolean | string {
      if (this.param?.paramType.type.includes('UINT')) {
        if (input < 0) {
          return 'This parameter must be a positive Integer'
        }
      }
      if (this.param?.paramType.type.includes('INT')) {
        if (!Number.isInteger(input)) {
          return 'This parameter must be an Integer'
        }
      }
      return true
    },
    updateSelectedFlags(): void {
      if (this.new_value < 0) {
        // No bitmask checking for negative values
        return
      }
      const output = []
      for (let v = 0; v < 64; v += 1) {
        const bitmask_value = 2 ** v
        // eslint-disable-next-line no-bitwise
        if (this.new_value & bitmask_value) {
          output.push(bitmask_value)
        }
      }
      this.selected_bitflags = output
    },
    async rebootVehicle(): Promise<void> {
      await this.restart_autopilot()
      autopilot_data.reset()
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
    async saveEditedParam(reboot = false) {
      if (!this.forcing_input && !this.isFormValid()) {
        return
      }
      this.showDialog(false)
      if (this.param == null) {
        return
      }
      if (!this.custom_input && this.param.bitmask !== undefined) {
        this.new_value = this.edited_bitmask_value
      }
      let value = 0
      if (typeof this.new_value === 'string') {
        value = parseFloat(this.new_value)
      } else {
        value = this.new_value
      }

      mavlink2rest.setParam(this.param.name, value, autopilot_data.system_id, this.param.paramType.type)

      if (reboot) {
        await this.rebootVehicle()
        autopilot_data.setRebootRequired(false)
      } else if (this.param.rebootRequired) {
        autopilot_data.setRebootRequired(true)
      }
    },
    showDialog(state: boolean) {
      this.$emit('change', state)
    },
    updateVariablesAtStart(): void {
      // Remove forcing_input once option is inside valid range
      if (this.forcing_input && typeof this.isInRange(this.new_value) === 'boolean') {
        this.forcing_input = false
      }
      this.updateVariables()
      this.isFormValid()
    },
    updateVariables(): void {
      // Select custom input if value is outside of possible options
      // Remove custom once value is known
      if (this.custom_input) {
        this.custom_input = !Object.keys(this.param?.options ?? [])
          .map((value) => parseFloat(value))
          .includes(this.new_value)
      }
      // Update form validation
      this.isFormValid()
    },
  },
})
</script>
