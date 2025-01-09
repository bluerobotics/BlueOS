<template>
  <div class="d-flex align-center">
    <span>{{ label }}</span>
    <v-tooltip bottom>
      <template #activator="{ on, attrs }">
        <v-icon
          small
          class="ml-2"
          v-bind="attrs"
          v-on="on"
        >
          mdi-information
        </v-icon>
      </template>
      <div>
        <strong>{{ param?.name }}</strong><br>
        <span v-if="param?.description">Description: {{ param.description }}<br></span>
        <span v-if="param?.range">Range: {{ param.range.low }} to {{ param.range.high }}<br></span>
        <span v-if="param?.units">Units: {{ param.units }}<br></span>
        <span v-if="param?.options">Options: {{ formatOptions }}<br></span>
        <span v-if="param?.rebootRequired">Requires reboot</span>
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
      type: Object as PropType<Parameter>,
      required: true,
    },
    formatOptions: {
      type: String,
      required: true,
    },
  },
})
</script>
