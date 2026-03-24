<template>
  <v-card class="battery-card mb-4" elevation="2">
    <v-card-title class="d-flex align-center">
      <v-icon left>
        mdi-battery
      </v-icon>
      {{ title }}
      <v-spacer />
      <span v-if="voltage != null" class="subtitle-1">
        {{ voltage.toFixed(2) }} V / {{ (current ?? 0).toFixed(2) }} A
      </span>
    </v-card-title>
    <v-card-text>
      <v-row dense align="center">
        <v-col cols="5" class="label-col">
          <parameter-label label="Battery Monitor" :param="monitorParam" />
        </v-col>
        <v-col cols="7">
          <inline-parameter-editor
            :param="monitorParam"
            :auto-set="true"
          />
        </v-col>
      </v-row>

      <template v-if="monitor_enabled">
        <v-divider class="my-2" />

        <v-row dense align="center">
          <v-col cols="5" class="label-col">
            Power Sensor
          </v-col>
          <v-col cols="7">
            <v-select
              v-model="selected_sensor"
              :items="sensor_options"
              dense
              hide-details
              @change="applySensorPreset"
            />
          </v-col>
        </v-row>

        <v-btn
          text
          x-small
          class="mt-2"
          @click="show_advanced = !show_advanced"
        >
          <v-icon left x-small>
            {{ show_advanced ? 'mdi-chevron-up' : 'mdi-chevron-down' }}
          </v-icon>
          {{ show_advanced ? 'Hide' : 'Show' }} Advanced
        </v-btn>

        <v-expand-transition>
          <div v-if="show_advanced">
            <v-divider class="my-2" />

            <v-row v-if="voltPinParam" dense align="center">
              <v-col cols="5" class="label-col">
                <parameter-label label="Voltage Pin" :param="voltPinParam" />
              </v-col>
              <v-col cols="7">
                <inline-parameter-editor
                  :param="voltPinParam"
                  :auto-set="true"
                />
              </v-col>
            </v-row>

            <v-row v-if="currPinParam" dense align="center">
              <v-col cols="5" class="label-col">
                <parameter-label label="Current Pin" :param="currPinParam" />
              </v-col>
              <v-col cols="7">
                <inline-parameter-editor
                  :param="currPinParam"
                  :auto-set="true"
                />
              </v-col>
            </v-row>

            <v-row v-if="voltMultParam" dense align="center">
              <v-col cols="5" class="label-col">
                <parameter-label label="Voltage Multiplier" :param="voltMultParam" />
              </v-col>
              <v-col cols="7" class="d-flex align-center">
                <div class="flex-grow-1">
                  <inline-parameter-editor
                    :param="voltMultParam"
                    :auto-set="true"
                  />
                </div>
                <v-btn
                  v-if="voltage != null"
                  x-small
                  color="primary"
                  class="ml-2"
                  @click="show_voltage_calc = true"
                >
                  Calculate
                </v-btn>
              </v-col>
            </v-row>

            <v-alert
              v-if="voltMultParam"
              type="info"
              dense
              text
              class="my-1 caption"
            >
              If the reported voltage differs from a voltmeter reading, adjust the multiplier.
            </v-alert>

            <v-row v-if="ampPerVoltParam" dense align="center">
              <v-col cols="5" class="label-col">
                <parameter-label label="Amps per Volt" :param="ampPerVoltParam" />
              </v-col>
              <v-col cols="7" class="d-flex align-center">
                <div class="flex-grow-1">
                  <inline-parameter-editor
                    :param="ampPerVoltParam"
                    :auto-set="true"
                  />
                </div>
                <v-btn
                  v-if="voltage != null"
                  x-small
                  color="primary"
                  class="ml-2"
                  @click="show_current_calc = true"
                >
                  Calculate
                </v-btn>
              </v-col>
            </v-row>

            <v-row v-if="ampOffsetParam" dense align="center">
              <v-col cols="5" class="label-col">
                <parameter-label label="Amps Offset" :param="ampOffsetParam" />
              </v-col>
              <v-col cols="7">
                <inline-parameter-editor
                  :param="ampOffsetParam"
                  :auto-set="true"
                />
              </v-col>
            </v-row>

            <v-alert
              v-if="ampOffsetParam"
              type="info"
              dense
              text
              class="my-1 caption"
            >
              Adjust if the vehicle reports current draw when there is none flowing.
            </v-alert>
          </div>

          <v-row v-if="capacityParam" dense align="center">
            <v-col cols="5" class="label-col">
              <parameter-label label="Battery Capacity" :param="capacityParam" />
            </v-col>
            <v-col cols="7">
              <inline-parameter-editor
                :param="capacityParam"
                :auto-set="true"
              />
            </v-col>
          </v-row>

          <v-row v-if="armVoltParam" dense align="center">
            <v-col cols="5" class="label-col">
              <parameter-label label="Min Arming Voltage" :param="armVoltParam" />
            </v-col>
            <v-col cols="7">
              <inline-parameter-editor
                :param="armVoltParam"
                :auto-set="true"
              />
            </v-col>
          </v-row>
        </v-expand-transition>

        <v-dialog v-model="show_voltage_calc" max-width="400">
          <v-card class="pa-4">
            <v-card-title class="subtitle-1 font-weight-bold">
              Calculate Voltage Multiplier
            </v-card-title>
            <v-card-text>
              <p class="body-2">
                Measure battery voltage with an external voltmeter and enter it below.
              </p>
              <v-text-field
                v-model.number="measured_voltage"
                label="Measured Voltage (V)"
                type="number"
                step="0.01"
                dense
                hide-details
                class="mb-3"
              />
              <div v-if="voltage != null" class="body-2 mb-1">
                <b>Vehicle Voltage:</b> {{ voltage.toFixed(3) }} V
              </div>
              <div v-if="voltMultParam" class="body-2">
                <b>Current Multiplier:</b> {{ voltMultParam.value }}
              </div>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn text small @click="show_voltage_calc = false">
                Cancel
              </v-btn>
              <v-btn
                small
                color="primary"
                :disabled="!can_calculate_voltage"
                @click="calculateVoltageMultiplier"
              >
                Calculate &amp; Set
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <v-dialog v-model="show_current_calc" max-width="400">
          <v-card class="pa-4">
            <v-card-title class="subtitle-1 font-weight-bold">
              Calculate Amps per Volt
            </v-card-title>
            <v-card-text>
              <p class="body-2">
                Measure current draw with an external current meter and enter it below.
              </p>
              <v-text-field
                v-model.number="measured_current"
                label="Measured Current (A)"
                type="number"
                step="0.01"
                dense
                hide-details
                class="mb-3"
              />
              <div v-if="current != null" class="body-2 mb-1">
                <b>Vehicle Current:</b> {{ current.toFixed(3) }} A
              </div>
              <div v-if="ampPerVoltParam" class="body-2">
                <b>Current Amps/Volt:</b> {{ ampPerVoltParam.value }}
              </div>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn text small @click="show_current_calc = false">
                Cancel
              </v-btn>
              <v-btn
                small
                color="primary"
                :disabled="!can_calculate_current"
                @click="calculateAmpsPerVolt"
              >
                Calculate &amp; Set
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </template>
    </v-card-text>
  </v-card>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

interface SensorPreset {
  text: string
  voltPin: number
  currPin: number
  voltMult: number
  ampPerVolt: number
  ampOffset: number
}

const SENSOR_PRESETS: SensorPreset[] = [
  {
    text: 'Power Module 90A',
    voltPin: 2,
    currPin: 3,
    voltMult: 10.1,
    ampPerVolt: 17.0,
    ampOffset: 0,
  },
  {
    text: 'Power Module HV',
    voltPin: 2,
    currPin: 3,
    voltMult: 12.02,
    ampPerVolt: 39.877,
    ampOffset: 0,
  },
  {
    text: '3DR Iris',
    voltPin: 2,
    currPin: 3,
    voltMult: 12.02,
    ampPerVolt: 17.0,
    ampOffset: 0,
  },
  {
    text: 'Blue Robotics Power Sense Module',
    voltPin: 2,
    currPin: 3,
    voltMult: 11.000,
    ampPerVolt: 37.8788,
    ampOffset: 0.330,
  },
  {
    text: 'Navigator w/ Blue Robotics Power Sense Module',
    voltPin: 5,
    currPin: 4,
    voltMult: 11.000,
    ampPerVolt: 37.8788,
    ampOffset: 0.330,
  },
]

export default Vue.extend({
  name: 'BatteryCard',
  components: {
    'inline-parameter-editor': () => import('@/components/parameter-editor/InlineParameterEditor.vue'),
    ParameterLabel: () => import('@/components/parameter-editor/ParameterLabel.vue'),
  },
  props: {
    title: { type: String, required: true },
    monitorParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    capacityParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    armVoltParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    voltPinParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    currPinParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    voltMultParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    ampPerVoltParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    ampOffsetParam: { type: Object as PropType<Parameter | undefined>, default: undefined },
    voltage: { type: Number as PropType<number | undefined>, default: undefined },
    current: { type: Number as PropType<number | undefined>, default: undefined },
  },
  data() {
    return {
      selected_sensor: null as string | null,
      show_advanced: false,
      show_voltage_calc: false,
      show_current_calc: false,
      measured_voltage: null as number | null,
      measured_current: null as number | null,
    }
  },
  computed: {
    monitor_enabled(): boolean {
      return this.monitorParam != null && this.monitorParam.value !== 0
    },
    sensor_options(): string[] {
      return [...SENSOR_PRESETS.map((p) => p.text), 'Other']
    },
    can_calculate_voltage(): boolean {
      return this.measured_voltage != null && this.measured_voltage > 0
        && this.voltage != null && this.voltage !== 0
    },
    can_calculate_current(): boolean {
      return this.measured_current != null && this.measured_current > 0
        && this.current != null && this.current !== 0
    },
    sensor_fingerprint(): string {
      return [
        this.voltPinParam?.value,
        this.currPinParam?.value,
        this.voltMultParam?.value,
        this.ampPerVoltParam?.value,
        this.ampOffsetParam?.value,
      ].join(',')
    },
  },
  watch: {
    monitor_enabled: {
      immediate: true,
      handler() {
        if (this.monitor_enabled) {
          this.detectCurrentSensor()
        }
      },
    },
    sensor_fingerprint() { this.detectCurrentSensor() },
  },
  methods: {
    detectCurrentSensor() {
      if (!this.voltPinParam || !this.currPinParam || !this.voltMultParam || !this.ampPerVoltParam) {
        return
      }
      for (const preset of SENSOR_PRESETS) {
        if (preset.voltPin === this.voltPinParam.value
          && preset.currPin === this.currPinParam.value
          && preset.voltMult === this.voltMultParam.value
          && preset.ampPerVolt === this.ampPerVoltParam.value
          && preset.ampOffset === (this.ampOffsetParam?.value ?? 0)) {
          this.selected_sensor = preset.text
          return
        }
      }
      this.selected_sensor = 'Other'
      this.show_advanced = true
    },
    applySensorPreset(selected: string) {
      const preset = SENSOR_PRESETS.find((p) => p.text === selected)
      if (!preset) return

      const { system_id } = autopilot_data
      if (this.voltPinParam) mavlink2rest.setParam(this.voltPinParam.name, preset.voltPin, system_id)
      if (this.currPinParam) mavlink2rest.setParam(this.currPinParam.name, preset.currPin, system_id)
      if (this.voltMultParam) mavlink2rest.setParam(this.voltMultParam.name, preset.voltMult, system_id)
      if (this.ampPerVoltParam) mavlink2rest.setParam(this.ampPerVoltParam.name, preset.ampPerVolt, system_id)
      if (this.ampOffsetParam) mavlink2rest.setParam(this.ampOffsetParam.name, preset.ampOffset, system_id)
    },
    calculateVoltageMultiplier() {
      if (!this.can_calculate_voltage || !this.voltMultParam) return
      const newMult = this.measured_voltage! * this.voltMultParam.value / this.voltage!
      mavlink2rest.setParam(this.voltMultParam.name, newMult, autopilot_data.system_id)
      this.show_voltage_calc = false
      this.measured_voltage = null
    },
    calculateAmpsPerVolt() {
      if (!this.can_calculate_current || !this.ampPerVoltParam) return
      const newApv = this.measured_current! * this.ampPerVoltParam.value / this.current!
      mavlink2rest.setParam(this.ampPerVoltParam.name, newApv, autopilot_data.system_id)
      this.show_current_calc = false
      this.measured_current = null
    },
  },
})
</script>

<style scoped>
.label-col {
  text-align: right;
  font-weight: 500;
}
</style>

<style>
.battery-card .v-text-field .v-label,
.battery-card .v-select .v-label {
  display: none;
}
</style>
