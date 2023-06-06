<template>
  <v-stepper vertical>
    <v-stepper-step
      v-for="(config, index) in configurations"
      :key="index"
      :step="index + 1"
      :color="getStepColor(config)"
      :complete-icon="getStepIcon(config)"
      :complete="true"
      active
      class="step-label"
    >
      {{ config.title }}
      <small v-if="config.summary">{{ config.summary }}</small>
      <small v-if="config.message" :color="getStepColor(config)">Error: {{ config.message }}</small>
    </v-stepper-step>
  </v-stepper>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

export type ConfigurationStatus = string | undefined

export interface Configuration {
  title: string,
  summary: string | undefined,
  promise: () => Promise<ConfigurationStatus>
  message: undefined | string
  done: boolean
}

export default Vue.extend({
  name: 'ActionStepper',
  props: {
    configurations: {
      type: Array as PropType<Configuration[]>,
      default: () => [],
    },
  },
  methods: {
    getStepIcon(config: Configuration) {
      if (config.done) {
        return 'mdi-check'
      }
      if (config.message === undefined) {
        return 'mdi-loading'
      }
      return 'mdi-alert'
    },
    getStepColor(config: Configuration) {
      if (config.done) {
        return 'success'
      }
      if (config.message === undefined) {
        return 'yellow'
      }
      return 'error'
    },
  },
})
</script>

<style scoped>
.step-label {
  text-shadow: 0px 0px 0px !important;
}
</style>
