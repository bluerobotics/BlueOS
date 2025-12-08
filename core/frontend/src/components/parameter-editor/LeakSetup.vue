<template>
  <v-card class="mt-4 mb-4">
    <v-card-text>
      <v-row align="center">
        <v-col cols="12">
          <span class="text-h6">Leak {{ leak_number }}</span>
        </v-col>
      </v-row>

      <v-row align="center">
        <v-col v-if="type_parameter" cols="4">
          <inline-parameter-editor
            :param="type_parameter"
            label="Sensor type"
            auto-set
          />
        </v-col>
        <v-col v-if="logic_parameter" cols="4">
          <inline-parameter-editor
            :param="logic_parameter"
            label="Logic when dry"
            auto-set
          />
        </v-col>
        <v-col v-if="failsafe_parameter" cols="4">
          <inline-parameter-editor
            :param="failsafe_parameter"
            label="Failsafe action"
            auto-set
          />
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue from 'vue'

import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'

export default Vue.extend({
  name: 'LeakSetup',
  components: {
    InlineParameterEditor,
  },
  props: {
    leakParameter: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  computed: {
    leak_number(): number {
      return parseInt(this.leakParameter.name.match(/LEAK(\d+)_TYPE/)?.[1] ?? '0', 10)
    },
    type_parameter(): Parameter | undefined {
      return autopilot_data.parameter(`LEAK${this.leak_number}_TYPE`)
    },
    logic_parameter(): Parameter | undefined {
      return autopilot_data.parameter(`LEAK${this.leak_number}_LOGIC`)
    },
    failsafe_parameter(): Parameter | undefined {
      return autopilot_data.parameter('FS_LEAK_ENABLE')
    },
  },
})
</script>
