<template>
  <div class="d-flex align-center">
    <v-row>
      <v-col cols="6">
        <span class="text-h6">Joystick Steps</span>
      </v-col>
      <v-col cols="6">
        <inline-parameter-editor
          :label="steps_param?.name"
          :param="steps_param"
        />
      </v-col>
      <servo-function-range-editor
        :param="param"
      />
    </v-row>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'
import ServoFunctionRangeEditor from './ServoFunctionRangeEditor.vue'

export default Vue.extend({
  name: 'ServoFunctionLightsEditor',
  components: {
    InlineParameterEditor,
    ServoFunctionRangeEditor,
  },
  props: {
    param: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  computed: {
    steps_param(): Parameter | undefined {
      return autopilot.parameter('JS_LIGHTS_STEPS')
    },
  },
})
</script>
