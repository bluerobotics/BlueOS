<template>
  <div class="d-flex align-center">
    <span :class="{ 'text--disabled': !param }">{{ label }}</span>
    <v-tooltip bottom>
      <template #activator="{ on, attrs }">
        <v-icon
          small
          class="ml-2"
          :color="param ? undefined : 'warning'"
          v-bind="attrs"
          v-on="on"
        >
          {{ param ? 'mdi-information' : 'mdi-alert-circle-outline' }}
        </v-icon>
      </template>
      <div v-if="param">
        <strong>{{ param.name }}</strong><br>
        <span v-if="param.description">Description: {{ param.description }}<br></span>
        <span v-if="param.range">Range: {{ param.range.low }} to {{ param.range.high }}<br></span>
        <span v-if="param.units">Units: {{ param.units }}<br></span>
        <span v-if="param.options">Options: {{ formatOptions ?? formattedOptions }}<br></span>
        <span v-if="param.rebootRequired">Requires reboot</span>
      </div>
      <div v-else>
        Parameter not found. It may not be available on this vehicle or firmware version.
      </div>
    </v-tooltip>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'ParameterLabel',
  props: {
    label: {
      type: String,
      required: true,
    },
    param: {
      type: Object as PropType<Parameter | undefined>,
      default: undefined,
      required: false,
    },
    formatOptions: {
      type: String as PropType<string | null>,
      default: null,
      required: false,
    },
  },
  computed: {
    formattedOptions(): string {
      if (this.param?.options) {
        return Object.entries(this.param.options).map(([key, value]) => `${key}: ${value}`).join('\n')
      }
      return ''
    },
  },
})
</script>
