<template>
  <div>
    <v-card class="mt-4">
      <v-card-title>
        <h4>{{ t`Select compasses to calibrate` }} </h4>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12">
            <div v-for="device in devices" :key="device.param">
              <!-- eslint-disable-next-line max-len -->
              <div v-if="calibration_slots[device.param] === undefined" v-tooltip="t`This compass is not in the priority list and cannot be calibrated. Drag it higher (by the dots) to assign it a priority.`">
                <v-checkbox
                  :input-value="false"
                  dense
                  disabled
                  :label="device.deviceName"
                />
              </div>
              <v-checkbox
                v-else
                v-model="selected_devices"
                dense
                :label="device.deviceName"
                :value="device.param"
                :background-color="getCompassColor(device.deviceIdNumber - 1)"
              />
            </div>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import { Dictionary } from '@/types/common'
import { deviceId } from '@/utils/deviceid_decoder'

import { compassCalibrationSlot } from './compassPriority'

export default Vue.extend({
  name: 'CompassMaskPicker',
  model: {
    prop: 'bitmask',
    event: 'input',
  },
  props: {
    devices: {
      type: Array as PropType<deviceId[]>,
      required: true,
      default: () => [],
    },
  },
  data() {
    return {
      selected_devices: [] as string[],
      compass_colors: ['#00ff0055', '#0000ff55', '#80008055'],
    }
  },
  computed: {
    calibration_slots(): Dictionary<number | undefined> {
      return Object.fromEntries(this.devices.map((device) => [device.param, compassCalibrationSlot(device)]))
    },
  },
  watch: {
    selected_devices() {
      this.emitBitmask()
    },
    calibration_slots() {
      const valid_devices = this.selected_devices.filter((param) => this.calibration_slots[param] !== undefined)
      if (valid_devices.length !== this.selected_devices.length) {
        this.selected_devices = valid_devices
        return
      }
      this.emitBitmask()
    },
  },
  mounted() {
    this.selected_devices = this.devices
      .filter((device) => this.calibration_slots[device.param] !== undefined)
      .map((device) => device.param)
  },
  methods: {
    emitBitmask(): void {
      const bitmask = this.selected_devices.reduce((acc, param) => {
        const slot = this.calibration_slots[param]
        return slot === undefined ? acc : acc | 1 << slot
      }, 0)
      this.$emit('input', bitmask)
    },
    getCompassColor(index: number): string {
      return this.compass_colors[index % this.compass_colors.length]
    },
  },
})
</script>
