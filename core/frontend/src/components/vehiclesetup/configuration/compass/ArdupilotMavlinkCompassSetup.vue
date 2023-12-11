<template>
  <v-card v-if="params_finished_loaded">
    <div class="d-flex flex-col">
      <v-card outline class="pa-2 mt-4 mr-2 mb-2 flex-shrink-1">
        <compass-display :compasses="reordered_compasses" :colors="compass_colors" />
        <v-card class="pa-2 ma-2" width="300px">
          <v-card-title>
            Declination
          </v-card-title>
          <v-card-text class="flex-shrink-1">
            <parameter-switch label="Auto Declination" :parameter="compass_autodec" />
            <p>
              If you enable this option, the autopilot will automatically set the declination based on your current
              location. A GPS or other absolute positioning system is required.
            </p>
            <v-text-field
              label="Current Declination"
              :disabled="compass_autodec?.value !== 0"
              :value="printParam(compass_dec)"
              @click="openParameterEditor(compass_dec)"
            />
          </v-card-text>
        </v-card>
      </v-card>
      <v-card outline class="pa-2 mt-4 mr-2 mb-2">
        <v-card-title>
          <h3>Compass Calibration</h3>
        </v-card-title>
        <v-card-text>
          <div class="d-flex flex-column">
            <v-expansion-panels>
              <v-expansion-panel>
                <v-expansion-panel-header>
                  Quick Compass Calibration
                </v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    This does a "quick" calibration of your compass.
                    You need to point your vehicle North,and then click the button.
                    This results in a much less accurate calibration, but is also much faster.
                    It can be a good starting point for calibration, followed by <b>CompassLearn</b>.
                  </p>
                  <large-vehicle-compass-calibrator :compasses="compasses" />
                </v-expansion-panel-content>
              </v-expansion-panel>

              <v-expansion-panel>
                <v-expansion-panel-header>
                  Compass Learn
                </v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    This allows automatic "calibration" of compass offsets. You need to have a valid world position.
                    In order to use this option, click the following button and then driver the vehicle around until you
                    see the message <b>"CompassLearn: finished"</b>
                  </p>
                  <compass-learn :compasses="compasses" />
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header>
                  Onboard Calibration (Coming soon)
                </v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    This does a full calibration of the compasses.
                    It requires you to spin the vehicle around manually multiple times.
                    You need move the vehicle around in all 3 axis.
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header>
                  Log-based Calibration (Coming soon)
                </v-expansion-panel-header>
                <v-expansion-panel-content>
                  <p>
                    This used logs from previous flights to calibrate the compasses.
                    This usually gives the best results.
                    While it is not currently implemented here. It can be done either in
                    <a href="https://firmware.ardupilot.org/Tools/WebTools/">Ardupilot WebTools</a> and
                    <a href="https://plotbeta.ardupilot.org/">LogViewer</a>.
                  </p>
                </v-expansion-panel-content>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
        </v-card-text>
      </v-card>
    </div>
    <div class="d-flex flex-row">
      <v-tabs v-model="tab" vertical color="primary">
        <draggable v-model="reordered_compasses" handle=".drag-handle">
          <v-tab
            v-for="compass in reordered_compasses"
            :key="compass.deviceIdNumber"
            class="pl-0 pr-0 compass-tab pt-7 pb-7 mt-4 mb-4"
            outline
          >
            <v-icon lg start class="mr-2 mt-3 mb-3 drag-handle">
              mdi-drag-vertical
            </v-icon>
            <v-icon start class="mr-2" :style="`color:${compass_colors[compass.paramValue]}`">
              mdi-compass
            </v-icon>
            <div class="d-flex flex-column pa-3">
              {{ compass.deviceName }} <br />
              {{ compass_description[compass.param] }}
              <v-chip
                v-if="compass_is_calibrated[compass.param]"
                color="green"
                text-color="white"
                x-small
                class="calibration-chip"
              >
                Calibrated
              </v-chip>
              <v-chip v-else color="red" text-color="white" x-small>
                Needs Calibration
              </v-chip>
            </div>
          </v-tab>
        </draggable>
        <v-card outlined class="ml-auto mr-auto rounded-lg pa-3" style="max-width: 200px;">
          To change the order of the compasses, drag them up and down in this list using the drag handler.
          This Operation requires an autopilot restart.
        </v-card>
        <v-tab-item
          v-for="(compass, index) in compasses"
          v-show="tab === index"
          :key="index"
          transition="v-scroll-y-transition"
        >
          <v-card outlined class="pa-2 mt-4 compass-settings">
            <v-card-title>
              <h3>{{ compass.deviceName }}</h3>
            </v-card-title>
            <v-row>
              <v-col cols="6">
                <v-card class="pa-5 mt-3">
                  <h4>Settings</h4>
                  <div v-if="compass_use_param[index]">
                    <parameter-switch
                      label="Use Compass"
                      :parameter="compass_use_param[index]"
                    />
                  </div>
                  <div v-else>
                    This Compass is not in use, move it higher in the list in order to be able to use it
                  </div>
                  <b>External/Internal:</b>
                  <v-btn class="ml-8 mb-4 mt-2" fab x-small @click="openParameterEditor(compass_extern_param[index])">
                    <v-icon>
                      mdi-cog
                    </v-icon>
                  </v-btn>
                  {{ printParam(compass_extern_param[index]) }}
                  <br />

                  <template v-if="compass_extern_param[index]?.value ?? 0 === 0">
                    <b>Mounting Rotation:</b>
                    <v-btn class="ml-4" fab x-small @click="openParameterEditor(compass_orient_param[index])">
                      <v-icon>
                        mdi-cog
                      </v-icon>
                    </v-btn>
                    {{ printParam(compass_orient_param[index]) }}
                  </template>
                  <template v-else>
                    Same as the Autopilot's
                  </template>
                </v-card>
                <v-card class="pa-5">
                  <h4>Details</h4>
                  <p>Bus: 0x{{ compass.address }} @ {{ compass.busType }}{{ compass.bus }} </p>
                </v-card>
              </v-col>
              <v-col cols="6">
                <compass-params :index="index + 1" />
              </v-col>
            </v-row>
          </v-card>
        </v-tab-item>
      </v-tabs>
    </div>
    <parameter-editor-dialog
      v-model="edit_param_dialog"
      :param="edited_param"
    />
  </v-card>
  <spinning-logo v-else size="50%" :subtitle="`${loaded_params}/${total_params} parameters loaded`" />
</template>
<script lang="ts">
import Vue from 'vue'
import draggable from 'vuedraggable'
import {
  VCardText, VExpansionPanel, VTextField,
} from 'vuetify/lib'

import ParameterSwitch from '@/components/common/ParameterSwitch.vue'
import SpinningLogo from '@/components/common/SpinningLogo.vue'
import CompassDisplay from '@/components/vehiclesetup/configuration/compass/CompassDisplay.vue'
import CompassParams from '@/components/vehiclesetup/configuration/compass/CompassParams.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'
import { Dictionary } from '@/types/common'
import decode, { deviceId } from '@/utils/deviceid_decoder'

import CompassLearn from './CompassLearn.vue'
import LargeVehicleCompassCalibrator from './LargeVehicleCompassCalibrator.vue'

export default Vue.extend({
  name: 'MavlinkCompassSetup',
  components: {
    CompassDisplay,
    CompassLearn,
    CompassParams,
    draggable,
    VTextField,
    LargeVehicleCompassCalibrator,
    ParameterSwitch,
    SpinningLogo,
    VCardText,
    VExpansionPanel,
  },
  data() {
    return {
      tab: 0,
      color_options: ['green', 'blue', 'purple'],
      reordered_compasses: [] as deviceId[],
      edited_param: undefined as (undefined | Parameter),
      edit_param_dialog: false,
    }
  },
  computed: {
    compass_colors(): Dictionary<string> {
      const results = {} as Dictionary<string>
      // sort compasses baed on paramValue
      const sorted_compasses = [...this.compasses].sort((a, b) => a.paramValue - b.paramValue)
      for (const [index, compass] of sorted_compasses.entries()) {
        results[compass.paramValue] = this.color_options[index % this.color_options.length]
      }
      return results
    },
    params_finished_loaded(): boolean {
      return autopilot_data.finished_loading
    },
    loaded_params(): number {
      return autopilot_data.parameters_loaded
    },
    total_params(): number {
      return autopilot_data.parameters_total
    },
    compass_autodec(): Parameter | undefined {
      return autopilot_data.parameter('COMPASS_AUTODEC')
    },
    compass_dec(): Parameter | undefined {
      return autopilot_data.parameter('COMPASS_DEC')
    },
    compasses(): deviceId[] {
      return autopilot_data.parameterRegex('^COMPASS_DEV_ID.*')
        .filter((param) => param.value !== 0)
        .map((parameter) => decode(parameter.name, parameter.value))
    },
    compass_description(): Dictionary<string> {
      const results = {} as Dictionary<string>
      for (const [index, compass] of this.reordered_compasses.entries()) {
        // First we check the priority for this device
        let priority = 'Unused'
        // while we used tpo check PRIO_ID, we now use DEV_ID, as all changes
        // to PRIO_ID are reflected in DEV_ID after a reboot, which we request
        switch (index) {
          case 0:
            priority = '1st'
            break
          case 1:
            priority = '2nd'
            break
          case 2:
            priority = '3rd'
            break
          default:
            priority = 'Unused'
        }
        // Then we check if it is internal or external
        const extern_param_name = compass.deviceIdNumber === 1
          ? 'COMPASS_EXTERNAL' : `COMPASS_EXTERN${compass.deviceIdNumber}`
        const external = autopilot_data.parameter(extern_param_name)?.value === 1 ?? false
        const external_string = external ? 'external' : 'internal'
        results[compass.param] = `${priority} (${external_string})`
      }
      return results
    },
    compass_is_calibrated(): Dictionary<boolean> {
      const results = {} as Dictionary<boolean>
      for (const compass of this.compasses) {
        const compass_number = compass.param.split('COMPASS_DEV_ID')[1]
        const offset_params_names = [
          `COMPASS_OFS${compass_number}_X`,
          `COMPASS_OFS${compass_number}_Y`,
          `COMPASS_OFS${compass_number}_Z`,
        ]
        const diagonal_params_names = [
          `COMPASS_ODI${compass_number}_X`,
          `COMPASS_ODI${compass_number}_Y`,
          `COMPASS_ODI${compass_number}_Z`,
        ]

        const offset_params = offset_params_names.map(
          (name) => autopilot_data.parameter(name),
        )
        const diagonal_params = diagonal_params_names.map(
          (name) => autopilot_data.parameter(name),
        )
        if (offset_params.includes(undefined) || diagonal_params.includes(undefined)) {
          results[compass.param] = false
          continue
        }
        const scale_param_name = `COMPASS_SCALE${compass_number}`
        const scale_param = autopilot_data.parameter(scale_param_name)
        const is_at_default_offsets = offset_params.every((param) => param?.value === 0.0)
        const is_at_default_diagonals = diagonal_params.every((param) => param?.value === 0.0)
        results[compass.param] = offset_params.isEmpty() || diagonal_params.isEmpty()
          || !is_at_default_offsets || !is_at_default_diagonals || scale_param?.value !== 0.0
      }
      return results
    },
    compass_orient_param(): Parameter[] {
      const results = [] as Parameter[]
      for (let i = 1; i <= 3; i += 1) {
        const param_name = i === 1 ? 'COMPASS_ORIENT' : `COMPASS_ORIENT${i}`
        const param = autopilot_data.parameter(param_name)
        if (param) {
          results.push(param)
        }
      }
      return results
    },
    compass_use_param(): Parameter[] {
      const results = [] as Parameter[]
      for (let i = 1; i <= 3; i += 1) {
        const param_name = i === 1 ? 'COMPASS_USE' : `COMPASS_USE${i}`
        const param = autopilot_data.parameter(param_name)
        if (param) {
          results.push(param)
        }
      }
      return results
    },
    compass_extern_param(): Parameter[] {
      const results = [] as Parameter[]
      for (let i = 1; i <= 3; i += 1) {
        const param_name = i === 1 ? 'COMPASS_EXTERNAL' : `COMPASS_EXTERN${i}`
        const param = autopilot_data.parameter(param_name)
        if (param) {
          results.push(param)
        }
      }
      return results
    },
  },
  watch: {
    reordered_compasses() {
      const compasses = this.reordered_compasses
      for (const [index, compass] of compasses.entries()) {
        const param_name = `COMPASS_PRIO${index + 1}_ID`
        const param = autopilot_data.parameter(param_name)
        if (param?.value !== compass.paramValue) {
          mavlink2rest.setParam(param_name, compass.paramValue, autopilot_data.system_id)
          autopilot_data.setRebootRequired(true)
        }
      }
    },
  },
  mounted() {
    this.reordered_compasses = this.compasses
  },
  methods: {
    printParam,
    openParameterEditor(parameter: Parameter | undefined) {
      if (parameter) {
        this.edited_param = parameter
        this.edit_param_dialog = true
      }
    },
  },
})
</script>
<style scoped>
.chip-container {
  display: flex;
  flex-direction: column; /* Change the flex-direction to column */
  align-items: flex-start; /* Align items to the start */
}
.compass-tab.v-tab--active {
  border-bottom:  1px solid var(--v-primary-base);
  border-top: 1px solid var(--v-primary-base);
  border-left:  1px solid var(--v-primary-base);
  border-radius: 5px 0 0 5px;
  transform: translateX(5px);
}
.compass-tab {
  border-bottom:  1px solid var(--v-primary-base);
  border-top: 1px solid var(--v-primary-base);
  border-left:  1px solid var(--v-primary-base);
  border-radius: 5px 0 0 5px;
}

.calibration-chip {
  margin: auto;
}

.compass-settings {
  border-color: var(--v-primary-base);
}
</style>
