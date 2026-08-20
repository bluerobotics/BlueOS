<template>
  <v-card
    v-if="failsafe_valid_for_current_vehicle"
    elevation="2"
    :class="{
      'disabled-failsafe': is_disabled && !dependency_unmet,
      'unavailable-failsafe': dependency_unmet,
    }"
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
      <v-alert
        v-if="dependency_unmet || !all_required_params_are_available"
        type="warning"
        text
        dense
        class="mx-4 mb-2"
      >
        {{ dependency_message }}
      </v-alert>
      <div>
        <div v-for="param in failsafeDefinition.params" :key="param.name">
          <v-row class="justify-right">
            <v-col :key="param.name" class="action-col" cols="7">
              <v-icon v-if="param.icon">
                {{ param.icon }}
              </v-icon>
              {{ param.replacementTitle ?? param.name }}
            </v-col>
            <v-col :key="`${param.name}-editor`" cols="5" class="pt-1 pb-1">
              <inline-parameter-editor
                v-if="params[param.name] != null"
                :key="failsafeDefinition.name"
                :auto-set="true"
                :disabled="is_disabled && !dependency_unmet && !control_param_names.includes(param.name)"
                :param="params[param.name] ?? undefined"
              />
              <template v-else>
                <v-text-field
                  disabled
                  class="caption"
                  :value="`${param.name} not found`"
                />
              </template>
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
import autopilot from '@/store/autopilot_manager'
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
    params(): Record<string, Parameter | null> {
      return this.failsafeDefinition.params.reduce(
        (dict: Record<string, Parameter | null>, param: ParamDefinitions) => {
          dict[param.name] = autopilot_data.parameter(param.name) ?? null
          return dict
        },
        {},
      )
    },
    all_required_params_are_available(): boolean {
      return this.failsafeDefinition.params.every(
        (param) => autopilot_data.parameter(param.name) != null || param.optional,
      )
    },
    is_disabled(): boolean {
      if (this.is_battery_failsafe) {
        const lowOff = this.params.BATT_LOW_VOLT?.value === 0
          && (autopilot_data.parameter('BATT_LOW_MAH')?.value ?? 0) === 0
        const crtOff = this.params.BATT_CRT_VOLT?.value === 0
          && (autopilot_data.parameter('BATT_CRT_MAH')?.value ?? 0) === 0
        return lowOff && crtOff
      }
      const controlParam = this.findControlParam()
      if (!controlParam || this.params[controlParam.name] == null) {
        return false
      }
      return this.params[controlParam.name]?.value === 0
    },
    is_battery_failsafe(): boolean {
      return this.failsafeDefinition.params.some((param) => param.name === 'BATT_LOW_VOLT')
    },
    dependency_unmet(): boolean {
      const dep = this.failsafeDefinition.dependsOn
      if (!dep) {
        return false
      }
      // If the dependency parameter itself hasn't loaded yet, don't show a
      // spurious notice; once params load, this re-evaluates to the truth.
      const depParam = autopilot_data.parameter(dep.paramName)
      if (!depParam) {
        return false
      }
      return depParam.value === dep.disabledValue
    },
    failsafe_valid_for_current_vehicle(): boolean {
      const supported = this.failsafeDefinition.supportedVehicles
      if (!supported) {
        return true
      }
      const { firmware_vehicle_type } = autopilot
      if (firmware_vehicle_type == null) {
        return false
      }
      return supported.includes(firmware_vehicle_type)
    },
    dependency_message(): string {
      return this.failsafeDefinition.dependsOn?.message ?? ''
    },
    control_param_names(): string[] {
      if (this.is_battery_failsafe) {
        return ['BATT_LOW_VOLT', 'BATT_CRT_VOLT', 'BATT_LOW_MAH', 'BATT_CRT_MAH']
      }
      const name = this.findControlParam()?.name
      return name ? [name] : []
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

.disabled-failsafe,
.unavailable-failsafe {
  border: 1px solid var(--v-warning-base) !important;
  position: relative;
}

.disabled-failsafe:hover,
.unavailable-failsafe:hover {
  border-color: var(--v-warning-lighten1) !important;
  box-shadow: 0 2px 8px rgba(224, 166, 0, 0.2);
}

.disabled-failsafe::after,
.unavailable-failsafe::after {
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

.disabled-failsafe::after {
  content: 'DISABLED';
}

.unavailable-failsafe::after {
  content: 'UNAVAILABLE';
}

.disabled-failsafe .svg-icon,
.unavailable-failsafe .svg-icon {
  opacity: 0.7;
  filter: grayscale(30%);
}
</style>
