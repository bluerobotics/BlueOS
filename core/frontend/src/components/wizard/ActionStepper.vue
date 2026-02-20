<template>
  <v-stepper vertical min-width="100%">
    <div v-for="(config, index) in configurations" :key="index" class="step-container">
      <v-stepper-step
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
      <v-checkbox
        :input-value="!config.skip && !config.done"
        class="step-checkbox"
        :disabled="loading || configurations.every(c => c.done)"
        @change="config.skip = !$event"
      />
    </div>
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
  skip: boolean
  started: boolean
}

export default Vue.extend({
  name: 'ActionStepper',
  props: {
    configurations: {
      type: Array as PropType<Configuration[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  methods: {
    getStepIcon(config: Configuration) {
      if (config.skip) {
        return 'mdi-debug-step-over'
      }
      if (config.done) {
        return 'mdi-check'
      }
      if (config.message === undefined) {
        if (!config.started) {
          return 'mdi-arrow-right-bold'
        }
        return 'mdi-loading'
      }
      return 'mdi-alert'
    },
    getStepColor(config: Configuration) {
      if (config.skip) {
        return 'black'
      }
      if (config.done) {
        return 'success'
      }
      if (config.message === undefined) {
        if (!config.started) {
          return 'grey'
        }
        return 'yellow'
      }
      return 'error'
    },
  },
})
</script>

<style scoped>
.step-label {
  text-shadow: 0 0 0 !important;
}

.step-container {
  display: flex;
  align-items: center;
}

.step-checkbox {
  margin-left: auto;
}
</style>
