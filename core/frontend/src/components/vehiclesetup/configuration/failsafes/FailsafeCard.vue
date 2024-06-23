<template>
  <v-card
    v-if="all_required_params_are_available"
    elevation="2"
    class="mb-4 mt-4 pa-4 d-flex flex-row  flex-grow-0 justify-left failsafe-card"
  >
    <div class="ma-4">
      <!-- this is theoretically not safe, but we have a command that gives users root access, so... -->
      <!-- eslint-disable vue/no-v-html -->
      <i :class="`${svg_outside_style} svg-icon`" v-html="image" />
    </div>
    <div class="d-flex flex-column justify-center">
      <v-card-title> {{ failsafeDefinition.name }}</v-card-title>
      <v-card-text>
        {{ failsafeDefinition.generalDescription }}
      </v-card-text>
      <div>
        <div v-for="param in available_params" :key="param.name">
          <v-row class="justify-right">
            <v-col :key="param.name" class="action-col" cols="7">
              <v-icon v-if="param.icon">
                {{ param.icon }}
              </v-icon>
              {{ param.replacementTitle ?? param.name }}
            </v-col>
            <v-col :key="`${param.name}-editor`" cols="5" class="pt-1 pb-1">
              <inline-parameter-editor :key="failsafeDefinition.name" :auto-set="true" :param="params[param.name]" />
            </v-col>
          </v-row>
        </div>
      </div>
    </div>
  </v-card>
</template>

<script lang="ts">
import axios from 'axios'
import Vue, { PropType } from 'vue'
import { Dictionary } from 'vue-router/types/router.js'

import { FailsafeDefinition, ParamDefinitions } from '@/components/vehiclesetup/configuration/failsafes/types'
import autopilot_data from '@/store/autopilot'
import settings from '@/store/settings'
import Parameter from '@/types/autopilot/parameter'

export default Vue.extend({
  name: 'FailsafeCard',
  components: {
    'inline-parameter-editor': () => import('@/components/parameter-editor/InlineParameterEditor.vue'),
  },
  props: {
    failsafeDefinition: {
      type: Object as PropType<FailsafeDefinition>,
      required: true,
    },

  },
  data() {
    return {
      image: undefined as string | undefined,
    }
  },
  computed: {
    svg_outside_style(): string {
      return `mr-0 ${settings.is_dark_theme ? 'svg-outline-dark' : 'svg-outline-light'}`
    },
    params(): Dictionary<Parameter> {
      return autopilot_data.parameters
        .filter((param) => this.failsafeDefinition.params.map((parameter) => parameter.name)
          .includes(param.name))
        .reduce((dict: Dictionary<Parameter>, param: Parameter) => {
          dict[param.name] = param
          return dict
        }, {})
    },
    all_required_params_are_available(): boolean {
      return this.failsafeDefinition.params.every((param) => param.name in this.params || param.optional)
    },
    available_params(): ParamDefinitions[] {
      return this.failsafeDefinition.params.filter((param) => param.name in this.params)
    },
  },
  mounted() {
    this.loadImage()
  },
  methods: {
    loadImage() {
      axios.get(this.failsafeDefinition.image).then((response) => {
        this.image = response.data
      })
    },
  },

})
</script>

<style>

i.svg-icon svg {
  height: 100% !important;
  min-width: 180px;
}

i.svg-outline-dark path {
  fill: #d1eaf1;
}

i.svg-outline-light path {
  fill: #002f45;
}

.failsafe-card {
  margin-left: auto;
  margin-right: auto;
  width: 700px;
}

.action-col {
  text-align: end;
  margin: auto;
}
</style>
