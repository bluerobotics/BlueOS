<template>
  <div class="pa-3">
    <v-card>
      <div class="main-container d-flex flex-row">
        <v-card outline class="mr-2 mb-2 flex-shrink-1 d-flex flex-col">
          <div class="compass-container">
            <compass-display :compasses="reordered_compasses" :colors="compass_colors" />
          </div>
        </v-card>

        <v-card outline class="compass-calib-container mb-2">
          <v-card-title>
            <h3>Compass Calibration</h3>
          </v-card-title>
          <v-card-text>
            <div class="d-flex flex-column">
              <v-expansion-panels>
                <v-expansion-panel>
                  <v-expansion-panel-header>
                    Full (Onboard) Calibration
                  </v-expansion-panel-header>
                  <v-expansion-panel-content>
                    <p>
                      Perform a full calibration of the selected compass(es) by manually spinning
                      the vehicle around multiple times, about all 3 rotation axes.
                    </p>
                    <full-compass-calibrator :compasses="compasses" />
                  </v-expansion-panel-content>
                </v-expansion-panel>
                <v-expansion-panel>
                  <v-expansion-panel-header>
                    Large Vehicle Calibration
                  </v-expansion-panel-header>
                  <v-expansion-panel-content>
                    <p>
                      Perform a quick, low-accuracy calibration of the compass(es) by pointing
                      your vehicle North, then clicking the Calibrate button.
                      It can be a good starting point for calibration, followed by <b>Compass Learn</b>.
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
                      Automatically "learn" compass calibration offsets by driving the vehicle around until
                      enough data has been collected, and <b>"CompassLearn: finished"</b> is displayed.
                      A valid global region estimate is required.
                    </p>
                    <compass-learn :compasses="compasses" />
                  </v-expansion-panel-content>
                </v-expansion-panel>
                <v-expansion-panel>
                  <v-expansion-panel-header>
                    Log-based Calibration (Coming soon)
                  </v-expansion-panel-header>
                  <v-expansion-panel-content>
                    <p>
                      Calibrate the compass(es) using a previous flight log.
                      This usually gives the best results.
                      While it is not currently implemented here, the compass offset information can be
                      determined in the Log Browser page. Press the green play button on a log file,
                      click the three vertical dots in the sidebar, open the <b>Mag Fit Tool</b>,
                      specify the general global region where the log was created, then click "Fit"
                      for each compass you wish to calibrate. Resulting values can be copied across to
                      the COMPASS_* autopilot parameters.
                    </p>
                  </v-expansion-panel-content>
                </v-expansion-panel>
              </v-expansion-panels>
            </div>
          </v-card-text>
        </v-card>
        <v-card outline class="mr-2 ml-2 mb-2">
          <div class="d-block ma-3" style="width: 400px;">
            <v-expansion-panels focusable>
              <v-expansion-panel>
                <v-expansion-panel-header>
                  <b>Declination</b> ({{ declination_short }})
                  <v-spacer />
                </v-expansion-panel-header>
                <v-expansion-panel-content>
                  <parameter-switch label="Auto Declination" :parameter="compass_autodec" />
                  <p>
                    If you enable this option, the autopilot will automatically set the
                    declination based on your current location.
                    A GPS or other absolute positioning system is required.
                  </p>
                  <InlineParameterEditor v-if="compass_autodec?.value === 0" auto-set :param="compass_dec" />
                </v-expansion-panel-content>
              </v-expansion-panel>
              <v-expansion-panel>
                <v-expansion-panel-header>
                  <template #actions>
                    <v-icon v-if="coordinates_valid" color="success">
                      mdi-check-circle
                    </v-icon>
                    <v-icon v-else color="error">
                      mdi-alert
                    </v-icon>
                  </template>

                  <b>Global Position</b>
                  <v-spacer />
                </v-expansion-panel-header>
                <v-expansion-panel-content>
                  <auto-coordinate-detector v-model="coordinates" />
                </v-expansion-panel-content>
              </v-expansion-panel>
            </v-expansion-panels>
          </div>
        </v-card>
      </div>
      <div class="compass-reorder-container d-flex flex-row">
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
                  :color="compass_calibration_type[compass.param].color"
                  text-color="white"
                  x-small
                  class="calibration-chip"
                >
                  {{ compass_calibration_type[compass.param].calibration_short }}
                </v-chip>
              </div>
            </v-tab>
          </draggable>
          <v-card outlined class="ml-auto mr-auto rounded-lg pa-3" style="max-width: 200px;">
            Click-and-drag the dots to change the priority of the compass options.
            Adjusted compass priorities are applied once the autopilot restarts.
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
                    <v-alert text dense :type="compass_calibration_type[compass.param].alert">
                      {{ compass_calibration_type[compass.param].description }}
                    </v-alert>
                    <p />
                    <h4>Settings</h4>
                    <div v-if="compass_use_param[index]">
                      <parameter-switch
                        label="Use Compass"
                        :parameter="compass_use_param[index]"
                      />
                    </div>
                    <div v-else>
                      This Compass is not in use, drag it higher (by the dots) to be able to use it.
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
  </div>
</template>
<script lang="ts">
import Vue from 'vue'
import draggable from 'vuedraggable'
import {
  VCardText, VExpansionPanel,
} from 'vuetify/lib'

import ParameterSwitch from '@/components/common/ParameterSwitch.vue'
import InlineParameterEditor from '@/components/parameter-editor/InlineParameterEditor.vue'
import CompassDisplay from '@/components/vehiclesetup/configuration/compass/CompassDisplay.vue'
import CompassParams from '@/components/vehiclesetup/configuration/compass/CompassParams.vue'
import mavlink2rest from '@/libs/MAVLink2Rest'
import Listener from '@/libs/MAVLink2Rest/Listener'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'
import { Dictionary } from '@/types/common'
import decode, { deviceId } from '@/utils/deviceid_decoder'

import CompassLearn from './CompassLearn.vue'
import FullCompassCalibrator from './FullCompassCalibrator.vue'
import LargeVehicleCompassCalibrator from './LargeVehicleCompassCalibrator.vue'

enum CalibrationType {
  UNKNOWN = 'UNKNOWN',
  NOT_CALIBRATED = 'NOT_CALIBRATED',
  QUICK = 'QUICK',
  FULL_NO_WMM = 'FULL_NO_WMM',
  FULL = 'FULL',
}

interface CalibrationState {
  calibration: CalibrationType
  color: string
  alert: string
  description: string
  calibration_short: string
}

export default Vue.extend({
  name: 'MavlinkCompassSetup',
  components: {
    CompassDisplay,
    CompassLearn,
    CompassParams,
    draggable,
    LargeVehicleCompassCalibrator,
    ParameterSwitch,
    VCardText,
    VExpansionPanel,
    FullCompassCalibrator,
    InlineParameterEditor,
  },
  data() {
    return {
      tab: 0,
      color_options: ['green', 'blue', 'purple', 'red', 'orange', 'brown', 'grey', 'black'],
      coordinates: undefined as { lat: number, lon: number } | undefined,
      coordinates_valid: false,
      reordered_compasses: [] as deviceId[],
      edited_param: undefined as (undefined | Parameter),
      edit_param_dialog: false,
      gps_listener: undefined as Listener | undefined,
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
      results.GPS1 = 'grey'
      results.GPS2 = 'black'
      return results
    },
    declination_short(): string {
      if (this.compass_autodec?.value === 1) {
        return 'Automatic Declination'
      }
      return `${this.compass_dec?.value.toFixed(2) ?? 'N/A'} rad`
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
    compass_calibration_type(): Dictionary<CalibrationState> {
      const results = {} as Dictionary<CalibrationState>
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
          results[compass.param] = {
            calibration: CalibrationType.UNKNOWN,
            color: 'var(--v-error-darken1)',
            alert: 'error',
            description: 'Unable to get calibration status - something went wrong.',
            calibration_short: 'Unknown',
          }
          continue
        }
        const is_at_default_offsets = offset_params.every((param) => param?.value === 0.0)
        if (is_at_default_offsets) {
          results[compass.param] = {
            calibration: CalibrationType.NOT_CALIBRATED,
            color: 'var(--v-error-darken1)',
            alert: 'error',
            description: 'The compass is not calibrated - please calibrate it.',
            calibration_short: 'Calibration Needed',
          }

          continue
        }

        const is_at_default_diagonals = diagonal_params.every((param) => param?.value === 0.0)
        if (is_at_default_diagonals) {
          results[compass.param] = {
            calibration: CalibrationType.QUICK,
            color: 'var(--v-warning-darken1)',
            alert: 'warning',
            description: 'Quick Calibration is easier for large vehicles, but has worse '
  + 'performance - consider using log-based calibration afterwards, to refine results.',
            calibration_short: 'Calibrated (Quick)',
          }
          continue
        }

        const scale_param_name = `COMPASS_SCALE${compass_number}`
        const scale_param = autopilot_data.parameter(scale_param_name)
        const is_at_default_scale = scale_param?.value === 0.0

        if (is_at_default_scale) {
          results[compass.param] = {
            calibration: CalibrationType.FULL_NO_WMM,
            color: 'var(--v-warning-darken1)',
            alert: 'warning',
            description: 'Calibrated, but without a known (detected or specified) global region, '
            + 'so no corrections were applied from the internal World Magnetic Model (WMM). '
            + 'Consider retrying with a valid position to improve compass performance.',
            calibration_short: 'Calibrated (No WMM)',
          }
          continue
        }
        results[compass.param] = {
          calibration: CalibrationType.FULL,
          color: 'var(--v-success-base)',
          alert: 'success',
          description: 'Fully calibrated, including corrections from the internal World Magnetic Model (WMM) database.',
          calibration_short: 'Fully Calibrated',
        }
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
        if (param && param?.value !== compass.paramValue) {
          mavlink2rest.setParam(param_name, compass.paramValue, autopilot_data.system_id)
          autopilot_data.setRebootRequired(true)
        }
      }
    },
  },
  mounted() {
    this.reordered_compasses = this.compasses
    this.gps_listener = mavlink2rest.startListening('GLOBAL_POSITION_INT').setCallback((receivedMessage) => {
      if (receivedMessage.message.lat !== 0 || receivedMessage.message.lon !== 0) {
        this.coordinates_valid = true
      }
    }).setFrequency(0)
    mavlink2rest.requestMessageRate('GLOBAL_POSITION_INT', 1, autopilot_data.system_id)
  },
  beforeDestroy() {
    this.gps_listener?.discard()
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
.main-container {
  background-color: #135DA3AA !important;
}

.compass-container {
  margin-inline: 10px;
  margin-top: -20px
}

.compass-calib-container {
  width: 100%;
}

.compass-reorder-container {
  width: 100%;
  padding: 15px;
  margin-top: -15px;
}

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
