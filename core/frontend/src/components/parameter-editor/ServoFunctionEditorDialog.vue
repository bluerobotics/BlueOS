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

        <component
          :is="function_type"
          v-if="function_type"
          :param="param"
        />
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
import Vue, { VueConstructor } from 'vue'

import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'
import ServoFunctionActuatorEditor from './ServoFunctionActuatorEditor.vue'
import ServoFunctionGpioEditor from './ServoFunctionGpioEditor.vue'
import ServoFunctionLightsEditor from './ServoFunctionLightsEditor.vue'
import ServoFunctionMotorEditor from './ServoFunctionMotorEditor.vue'
import ServoFunctionRangeEditor from './ServoFunctionRangeEditor.vue'

export default Vue.extend({
  name: 'ServoFunctionEditorDialog',
  components: {
    InlineParameterEditor,
    ServoFunctionRangeEditor,
    ServoFunctionMotorEditor,
    ServoFunctionGpioEditor,
    ServoFunctionActuatorEditor,
    ServoFunctionLightsEditor,
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
  computed: {
    function_type(): VueConstructor<Vue> | undefined {
      const name = this.param.options?.[this.param.value]
      if (name?.toLowerCase().includes('motor')) {
        return ServoFunctionMotorEditor
      }
      if (name?.toLowerCase().includes('gpio')) {
        return ServoFunctionGpioEditor
      }
      if (name?.toLowerCase().includes('actuator')) {
        return ServoFunctionActuatorEditor
      }
      if (name?.toLowerCase().includes('lights')) {
        return ServoFunctionLightsEditor
      }
      if (name?.toLowerCase().includes('disabled')) {
        return undefined
      }
      return ServoFunctionRangeEditor
    },
  },
})
</script>
