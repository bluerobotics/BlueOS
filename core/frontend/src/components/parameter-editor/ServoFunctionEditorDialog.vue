<template>
  <v-dialog
    :value="value"
    max-width="600px"
    @input="$emit('input', $event)"
  >
    <v-card v-if="param?.name">
      <v-card-title>
        Parameter Editor
        <v-spacer />
        <v-btn
          icon
          @click="$emit('input', false)"
        >
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>

      <v-card-text>
        <inline-parameter-editor
          :auto-set="true"
          :label="param.name"
          :param="param"
        />

        <servo-function-range-editor :param="param" />
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn
          color="primary"
          @click="$emit('input', false)"
        >
          Close
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script lang="ts">
import Vue from 'vue'

import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'
import ServoFunctionRangeEditor from './ServoFunctionRangeEditor.vue'

export default Vue.extend({
  name: 'ServoFunctionEditorDialog',
  components: {
    InlineParameterEditor,
    ServoFunctionRangeEditor,
  },
  model: {
    prop: 'value',
    event: 'input',
  },
  props: {
    value: {
      type: Boolean,
      required: true,
    },
    param: {
      type: Object as () => Parameter,
      required: true,
    },
  },
})
</script>
