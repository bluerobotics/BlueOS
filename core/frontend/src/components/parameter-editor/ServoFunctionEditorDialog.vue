<template>
  <v-dialog
    :value="value"
    max-width="600px"
    @input="$emit('input', $event)"
  >
    <v-card>
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
          :label="param.name"
          :param="param"
        />
        <v-row>
          <v-col
            cols="12"
            sm="4"
          >
            <inline-parameter-editor
              :label="max_param?.name"
              :param="max_param"
            />
          </v-col>
          <v-col
            cols="12"
            sm="4"
          >
            <inline-parameter-editor
              :label="trim_param?.name"
              :param="trim_param"
            />
          </v-col>
          <v-col
            cols="12"
            sm="4"
          >
            <inline-parameter-editor
              :label="min_param?.name"
              :param="min_param"
            />
          </v-col>
        </v-row>
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

import autopilot from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'

export default Vue.extend({
  name: 'ServoFunctionEditorDialog',
  components: {
    InlineParameterEditor,
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
  data() {
    return {
      paramValues: {} as { [key: string]: string | number },
    }
  },
  computed: {
    trim_param(): Parameter | undefined {
      const name = this.param.name.replace('_FUNCTION', '_TRIM')
      return autopilot.parameter(name)
    },
    max_param(): Parameter | undefined {
      const name = this.param.name.replace('_FUNCTION', '_MAX')
      return autopilot.parameter(name)
    },
    min_param(): Parameter | undefined {
      const name = this.param.name.replace('_FUNCTION', '_MIN')
      return autopilot.parameter(name)
    },
  },
  watch: {
    param: {
      handler(newParam: Parameter) {
        // Initialize paramValues with current parameter values
        this.$set(this.paramValues, newParam.name, newParam.value)
      },
      immediate: true,
    },
  },
  methods: {

  },
})
</script>

<style scoped>
.parameter-card {
  margin-bottom: 12px;
}
</style>
