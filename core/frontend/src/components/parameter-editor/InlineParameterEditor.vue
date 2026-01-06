<template>
  <v-form
    ref="form"
    v-model="is_form_valid"
    @submit.prevent="saveEditedParam"
  >
    <div class="d-flex align-center">
      <div class="flex-grow-1">
        <!-- Bitmask checkboxes -->
        <template v-if="!custom_input && param?.bitmask">
          <v-checkbox
            v-for="(key, keyvalue) in param.bitmask"
            :key="keyvalue"
            v-model="selected_bitflags"
            dense
            hide-details
            :loading="waiting_for_param_update"
            :label="key"
            :value="2 ** keyvalue"
          />
        </template>

        <!-- Autocomplete for many options -->
        <v-autocomplete
          v-else-if="!custom_input && Object.entries(param?.options ?? []).length > 10"
          v-model.number="internal_new_value"
          variant="solo"
          :loading="waiting_for_param_update"
          :items="as_select_items"
        >
          <template #label>
            <parameter-label :label="label ?? 'Select an option'" :param="param" :format-options="formatOptions" />
          </template>
        </v-autocomplete>

        <!-- Select for few options -->
        <v-select
          v-else-if="!custom_input && param?.options"
          v-model.number="internal_new_value"
          dense
          :items="as_select_items"
          :indeterminate="waiting_for_param_update"
          @change="updateVariables"
        >
          <template #label>
            <parameter-label :label="label ?? 'Choose a value'" :param="param" :format-options="formatOptions" />
          </template>
        </v-select>

        <!-- Text input for numbers -->
        <v-text-field
          v-if="custom_input || (!param?.options && !param?.bitmask)"
          v-model="internal_new_value_as_string"
          dense
          type="number"
          :step="param.increment ?? 0.01"
          :suffix="param.units"
          :rules="forcing_input ? [] : [isInRange, isValidType]"
          :loading="waiting_for_param_update"
          @blur="updateVariables"
          @input="internal_new_value = parseFloat(internal_new_value_as_string)"
        >
          <template #label>
            <parameter-label :label="label ?? 'Enter a value'" :param="param" :format-options="formatOptions" />
          </template>
        </v-text-field>
      </div>
    </div>

    <v-divider v-if="show_advanced_checkbox || show_custom_checkbox" class="my-2" />
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
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'
import { Dictionary } from '@/types/common'

import ParameterLabel from './ParameterLabel.vue'

export default Vue.extend({
  name: 'InlineParameterEditor',
  components: {
    ParameterLabel,
  },
  model: {
    prop: 'newValue',
    event: 'change',
  },
  props: {
    param: {
      type: Object as PropType<Parameter> | undefined,
      default: undefined,
    },
    allowCustom: {
      type: Boolean,
      default: false,
    },
    autoSet: {
      type: Boolean,
      default: false,
    },
    label: {
      type: String as PropType<string | undefined>,
      default: undefined,
    },
    autoRefreshParams: {
      type: Boolean,
      default: false,
    },
    metadataOverrides: {
      type: Object as PropType<Dictionary<string>>,
      default: () => ({}),
    },
  },
  data() {
    return {
      custom_input: false,
      forcing_input: false,
      // Form can't be computed correctly, so we save it's state under data
      is_form_valid: false,
      internal_new_value: 0,
      internal_new_value_as_string: '',
      selected_bitflags: [] as number[],
      last_sent_value: undefined as number | undefined,
    }
  },
  computed: {
    as_select_items() {
      const entries = Object.entries(this.param?.options ?? [])
      const value_is_known = Object.keys(this.param?.options ?? []).map(parseFloat).includes(this.param?.value)
      const options = entries.map(([value, name]) => ({ text: name, value: parseFloat(value), disabled: false }))
      // replace entries in metadataOverrides
      for (const [value, _name] of entries) {
        if (value in this.metadataOverrides) {
          const index = options.findIndex((option) => option.value === parseFloat(value))
          options[index].text = this.metadataOverrides[value]
        }
      }
      if (!value_is_known) {
        options.push({ text: `Custom: ${this.param?.value}`, value: this.param?.value, disabled: false })
      }
      return options
    },
    edited_bitmask_value(): number {
      return this.selected_bitflags.reduce((accumulator, current) => accumulator + current, 0)
    },
    show_advanced_checkbox(): boolean {
      return typeof this.isInRange(this.internal_new_value ?? 0) === 'string'
    },
    show_custom_checkbox(): boolean {
      return !!(this.param?.options || this.param?.bitmask) && this.allowCustom
    },
    waiting_for_param_update(): boolean {
      if (!this.autoSet) {
        return false
      }
      // Don't show loading state if the value was just set and we're waiting for vehicle to catch up
      if (!this.last_sent_value || this.internal_new_value === this.last_sent_value) {
        return false
      }
      return this.param?.value !== this.internal_new_value
    },
    param_value() {
      return this.param?.value ?? 0
    },
    formatOptions(): string {
      if (!this.param?.options) {
        return ''
      }
      return Object.entries(this.param.options)
        .map(([value, name]) => `${value}: ${name}`)
        .join(', ')
    },
  },
  watch: {
    param(newParam) {
      this.internal_new_value = newParam?.value ?? 0
      this.internal_new_value_as_string = String(this.internal_new_value)
    },
    is_form_valid(valid) {
      this.$emit('form-valid-change', valid)
      if (!valid) {
        this.forcing_input = true
      }
    },
    internal_new_value() {
      if (this.autoSet) {
        this.saveEditedParam()
      }
      this.$emit('change', this.internal_new_value)
    },
    selected_bitflags() {
      this.internal_new_value = this.edited_bitmask_value
      this.updateVariables()
    },
    param_value() {
      this.updateSelectedFlags()
      if (this.last_sent_value === undefined) {
        this.internal_new_value = this.param_value
        this.internal_new_value_as_string = String(this.internal_new_value)
      }
    },
  },
  mounted() {
    this.internal_new_value = this.param?.value ?? 0
    this.updateVariables()
    this.updateSelectedFlags()
  },
  methods: {
    isInRange(input: number | string): boolean | string {
      // The input value is an empty string when the field is empty
      if (typeof input === 'string' && input?.trim().length === 0) {
        return 'This should be a number between min and max'
      }
      input = Number(input)

      if (!this.param?.range) {
        return true
      }

      if (this.param?.bitmask && input < 0) {
        return 'Value should be greater or equal to 0'
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
      if (!this.param?.bitmask) {
        return
      }
      const value = this.param.value ?? 0
      if (value < 0) {
        // No bitmask checking for negative values
        return
      }

      const output = []
      for (let bit = 0; bit < 64; bit += 1) {
        const bitmask_value = 2 ** bit
        // eslint-disable-next-line no-bitwise
        if (value & bitmask_value) {
          output.push(bitmask_value)
        }
      }
      this.selected_bitflags = output
    },

    async saveEditedParam() {
      if (this.param_value === this.internal_new_value) {
        return
      }
      if (!this.forcing_input && !this.is_form_valid) {
        return
      }
      if (this.param == null) {
        return
      }
      if (!this.custom_input && this.param?.bitmask !== undefined) {
        this.internal_new_value = this.edited_bitmask_value
      }
      let value = 0
      if (typeof this.internal_new_value === 'string') {
        value = parseFloat(this.internal_new_value)
      } else {
        value = this.internal_new_value
      }
      if (!this.autoSet) {
        this.$emit('changed', value)
        return
      }
      if (this.param?.rebootRequired) {
        autopilot_data.setRebootRequired(false)
      }
      this.last_sent_value = value
      mavlink2rest.setParam(this.param.name, value, autopilot_data.system_id, this.param.paramType.type)
      if (this.autoRefreshParams) {
        autopilot_data.reset()
      }
    },
    updateVariables(): void {
      // Select custom input if value is outside of possible options
      // Remove custom once value is known
      if (this.custom_input) {
        this.custom_input = !Object.keys(this.param?.options ?? [])
          .map((value) => parseFloat(value))
          .includes(this.internal_new_value)
      }
      if (this.param?.value) {
        this.internal_new_value_as_string = this.internal_new_value.toString()
      }

      this.saveEditedParam()
      if (!this.is_form_valid) {
        this.forcing_input = true
      }
    },
  },
})
</script>
