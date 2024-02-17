<template>
  <div>
    <v-switch v-model="switchValue" :label="label" />
  </div>
</template>
<script lang="ts">
import { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

export default {
  name: 'ParameterSwitch',
  props: {
    parameter: {
      type: Object as PropType<Parameter | undefined>,
      required: true,
    },
    offValue: {
      type: Number,
      default: 0,
    },
    onValue: {
      type: Number,
      default: 1,
    },
    label: {
      type: String,
      default: '',
    },
  },
  computed: {
    switchValue: {
      get(): boolean {
        return this.parameter?.value === this.onValue
      },
      set(newValue: boolean) {
        if (this.parameter === undefined) {
          return
        }
        mavlink2rest.setParam(
          this.parameter.name,
          newValue ? this.onValue : this.offValue,
          autopilot_data.system_id,
          this.parameter.paramType.type,
        )
      },
    },
  },
}
</script>
