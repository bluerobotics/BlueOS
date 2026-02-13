<template>
  <v-card
    v-if="all_required_params_are_available"
    elevation="2"
    :class="{ 'disabled-failsafe': is_disabled }"
    class="mb-4 mt-4 pa-4 d-flex flex-row  flex-grow-0 justify-left failsafe-card"
  >
    <div class="ma-4">
      <!-- this is theoretically not safe, but we have a command that gives users root access, so... -->
      <!-- eslint-disable vue/no-v-html -->
      <i class="svg-icon" v-html="image" />
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
              <inline-parameter-editor
                :key="failsafeDefinition.name"
                :auto-set="true"
                :disabled="is_disabled && param.name !== actionParamName"
                :param="params[param.name]"
              />
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

import { FailsafeDefinition, ParamDefinitions } from '@/components/vehiclesetup/configuration/failsafes/types'
import autopilot_data from '@/store/autopilot'
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
    params(): Record<string, Parameter> {
      return autopilot_data.parameters
        .filter((param) => this.failsafeDefinition.params.map((parameter) => parameter.name)
          .includes(param.name))
        .reduce((dict: Record<string, Parameter>, param: Parameter) => {
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
    is_disabled(): boolean {
      const controlParam = this.findControlParam()
      if (!controlParam || !(controlParam.name in this.params)) {
        return false
      }
      return this.params[controlParam.name].value === 0
    },
    actionParamName(): string | undefined {
      return this.findControlParam()?.name
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
    findControlParam(): ParamDefinitions | undefined {
      const enableParam = this.failsafeDefinition.params.find(
        (p) => p.replacementTitle === 'Enable' || p.name.includes('_ENABLE'),
      )
      if (enableParam) {
        return enableParam
      }

      return this.failsafeDefinition.params.find(
        (p) => p.replacementTitle === 'Action',
      )
    },
  },

})
</script>

<style>

i.svg-icon svg {
  height: 100% !important;
  min-width: 180px;
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

.disabled-failsafe {
  border: 1px solid var(--v-warning-base) !important;
  position: relative;
}

.disabled-failsafe:hover {
  border-color: var(--v-warning-lighten1) !important;
  box-shadow: 0 2px 8px rgba(224, 166, 0, 0.2);
}

.disabled-failsafe::after {
  content: 'DISABLED';
  position: absolute;
  top: 8px;
  right: 8px;
  background-color: var(--v-warning-base);
  color: white;
  padding: 3px 6px;
  border-radius: 3px;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.5px;
  z-index: 2;
  pointer-events: none;
}

.disabled-failsafe .svg-icon {
  opacity: 0.7;
  filter: grayscale(30%);
}
</style>
