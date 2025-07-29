<template>
  <div class="d-flex align-center">
    <div class="flex-grow-1">
      <v-checkbox
        v-model="internal_value"
        dense
        hide-details
        :indeterminate="waiting_for_param_update"
        :label="label ?? param?.name ?? 'Parameter not found'"
        :true-value="checkedValue"
        :false-value="uncheckedValue"
        @change="onCheckboxChange"
      />
    </div>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'ParameterCheckbox',
  model: {
    prop: 'value',
    event: 'change',
  },
  props: {
    param: {
      type: Object as PropType<Parameter>,
      required: true,
    },
    label: {
      type: String as PropType<string | undefined>,
      default: undefined,
    },
    checkedValue: {
      type: Number,
      default: 1,
    },
    uncheckedValue: {
      type: Number,
      default: 0,
    },
  },
  data() {
    return {
      internal_value: undefined as number | undefined,
      last_sent_value: undefined as number | undefined,
    }
  },
  computed: {
    waiting_for_param_update(): boolean {
      // Don't show loading state if the value was just set and we're waiting for vehicle to catch up
      if (!this.last_sent_value || this.param_value === this.last_sent_value) {
        return false
      }
      return this.param?.value !== this.internal_value
    },
    param_value(): number {
      return this.param?.value ?? this.uncheckedValue
    },
  },
  watch: {
    param(newParam) {
      if (newParam) {
        this.internal_value = newParam.value
      }
    },
    param_value() {
      if (this.last_sent_value === undefined) {
        this.internal_value = this.param_value
      }
    },
  },
  mounted() {
    this.internal_value = this.param?.value ?? this.uncheckedValue
  },
  methods: {
    onCheckboxChange(value: number): void {
      if (this.param_value === value) {
        return
      }
      this.internal_value = value
      this.saveEditedParam()
    },

    async saveEditedParam(): Promise<void> {
      if (this.param_value === this.internal_value) {
        return
      }
      if (this.param === undefined || this.internal_value === undefined) {
        return
      }
      if (this.param?.rebootRequired) {
        autopilot_data.setRebootRequired(true)
      }
      this.last_sent_value = this.internal_value

      await mavlink2rest.setParam(
        this.param.name,
        this.internal_value,
        autopilot_data.system_id,
        this.param.paramType.type,
      )
    },
  },
})
</script>
