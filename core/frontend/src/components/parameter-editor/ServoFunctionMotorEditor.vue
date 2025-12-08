<template>
  <div>
    <v-card class="mt-4 mb-4">
      <v-card-text>
        <div class="d-flex align-center mb-4">
          <span class="text-h6">Motor Configuration</span>
          <v-tooltip bottom>
            <template #activator="{ on, attrs }">
              <v-icon
                class="ml-2"
                small
                v-bind="attrs"
                v-on="on"
              >
                mdi-information
              </v-icon>
            </template>
            <span>Adjust the minimum, trim, and maximum PWM values for this motor</span>
          </v-tooltip>
        </div>
        <v-row class="mb-4">
          <v-col cols="6">
            <span class="text-h6">PWM Type</span>
          </v-col>
          <v-col cols="6">
            <inline-parameter-editor
              :auto-set="true"
              :label="mot_pwm_type_param?.name"
              :param="mot_pwm_type_param"
            />
          </v-col>
        </v-row>
        <v-row class="mb-4">
          <v-col cols="6">
            <span class="text-h6">Reverse Direction</span>
          </v-col>
          <v-col cols="6">
            <inline-parameter-editor
              :auto-set="true"
              :label="reverse_direction_param?.name"
              :param="reverse_direction_param"
            />
          </v-col>
        </v-row>
        <div
          v-if="mot_pwm_type_is_supported"
          ref="sliderContainer"
          class="servo-slider"
          @mousedown="onSliderMouseDown"
          @mousemove="onSliderMouseMove"
          @mouseup="onSliderMouseUp"
          @mouseleave="onSliderMouseUp"
          @touchstart="onTouchStart"
          @touchmove="onTouchMove"
          @touchend="onTouchEnd"
          @touchcancel="onTouchEnd"
        >
          <div class="slider-track" />
          <div
            class="slider-fill"
            :style="{ left: `${minPercent}%`, width: `${maxPercent - minPercent}%` }"
          />
        <div
          v-for="(thumbType, index) in ['min', 'trim', 'max']"
          v-show="thumbType !== 'trim' || trim_param"
          :key="thumbType"
          class="slider-thumb"
          :class="{ active: activeThumb === index }"
          :style="{ left: `${getThumbPosition(index)}%` }"
          @mousedown.stop="startDragging(index)"
        >
          <div class="thumb-label">
            {{ thumbType }}: {{ getThumbValue(index) }}
          </div>
        </div>
        </div>
        <v-alert
          v-else
          type="warning"
          class="mb-4"
        >
          PWM type is not supported by BlueOS.
        </v-alert>
      </v-card-text>
    </v-card>

    <v-row>
      <v-col
        cols="12"
        sm="4"
      >
        <v-card
          outlined
          class="parameter-card"
        >
          <v-card-text class="py-2">
            <inline-parameter-editor
              :auto-set="true"
              :label="min_param?.name"
              :param="min_param"
            />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col
        cols="12"
        sm="4"
      >
        <v-card
          outlined
          class="parameter-card"
          :disabled="!trim_param"
          :class="{ 'disabled-card': !trim_param }"
        >
          <v-card-text class="py-2">
            <inline-parameter-editor
              :auto-set="true"
              :label="trim_param?.name ?? 'Trim'"
              :param="trim_param"
            />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col
        cols="12"
        sm="4"
      >
        <v-card
          outlined
          class="parameter-card"
        >
          <v-card-text class="py-2">
            <inline-parameter-editor
              :auto-set="true"
              :label="max_param?.name"
              :param="max_param"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot from '@/store/autopilot'
import Parameter from '@/types/autopilot/parameter'

import InlineParameterEditor from './InlineParameterEditor.vue'

type ParamType = 'min' | 'trim' | 'max'
type ParamValueKey = 'minValue' | 'trimValue' | 'maxValue'

type ValueMap = Record<ParamType, ParamValueKey>
type ParamMap = Record<ParamType, string>

const MIN_PWM = 800
const MAX_PWM = 2200
const DEFAULT_MIN = 1000
const DEFAULT_TRIM = 1500
const DEFAULT_MAX = 2000

enum PwmTypes {
  Normal = 0,
  OneShot = 1,
  OneShot125 = 2,
  Brushed = 3,
  DShot150 = 4,
  DShot300 = 5,
  DShot600 = 6,
  DShot1200 = 7,
  PWMRange = 8,
  PWMAngle = 9,
}

export default Vue.extend({
  name: 'ServoFunctionMotorEditor',
  components: {
    InlineParameterEditor,
  },
  props: {
    param: {
      type: Object as () => Parameter,
      required: true,
    },
  },
  data() {
    return {
      minValue: DEFAULT_MIN,
      trimValue: DEFAULT_TRIM,
      maxValue: DEFAULT_MAX,
      activeThumb: -1,
      isDragging: false,
    }
  },
  computed: {
    motor_number(): number | undefined {
      const function_name = this.param.options?.[this.param.value] as string
      const motor_number = function_name.match(/\d+/)?.[0]
      if (!motor_number) return undefined
      return parseInt(motor_number)
    },
    trim_param(): Parameter | undefined {
      if (this.mot_pwm_type === PwmTypes.Normal) {
        return autopilot.parameter(`MOT_${this.motor_number}_TRIM`)
      }
      if (this.mot_pwm_type === PwmTypes.PWMAngle) {
        return this.getParamByType('_TRIM')
      }
      return undefined
    },
    max_param(): Parameter | undefined {
      return this.mot_pwm_type === PwmTypes.PWMAngle ? this.getParamByType('_MAX') : autopilot.parameter('MOT_PWM_MAX')
    },
    min_param(): Parameter | undefined {
      return this.mot_pwm_type === PwmTypes.PWMAngle ? this.getParamByType('_MIN') : autopilot.parameter('MOT_PWM_MIN')
    },
    mot_pwm_type_param(): Parameter | undefined {
      return autopilot.parameter('MOT_PWM_TYPE')
    },
    mot_pwm_type(): PwmTypes {
      const value = this.mot_pwm_type_param?.value as unknown as PwmTypes
      return value ?? PwmTypes.Normal
    },
    mot_pwm_type_is_supported(): boolean {
      return this.mot_pwm_type === PwmTypes.Normal || this.mot_pwm_type === PwmTypes.PWMAngle
    },
    reverse_direction_param(): Parameter | undefined {
      if (this.mot_pwm_type === PwmTypes.PWMAngle) {
        return this.getParamByType('_REVERSED')
      }
      if (this.mot_pwm_type === PwmTypes.Normal) {
        return autopilot.parameter(`MOT_${this.motor_number}_DIRECTION`)
      }
      return undefined
    },
    minPercent(): number {
      return this.calculatePercentage(this.minValue)
    },
    trimPercent(): number {
      return this.calculatePercentage(this.trimValue)
    },
    maxPercent(): number {
      return this.calculatePercentage(this.maxValue)
    },
  },
  watch: {
    param: {
      handler(newParam: Parameter) {
        if (!newParam?.name) return
        this.initializeSliderValues()
      },
      immediate: true,
    },
    'min_param.value': function onMinParamChange(newValue: number) {
      this.updateParamValue('min', newValue)
    },
    'trim_param.value': function onTrimParamChange(newValue: number) {
      this.updateParamValue('trim', newValue)
    },
    'max_param.value': function onMaxParamChange(newValue: number) {
      this.updateParamValue('max', newValue)
    },
  },
  methods: {
    getParamByType(type: string): Parameter | undefined {
      if (!this.param?.name) return undefined
      const name = this.param.name.replace('_FUNCTION', type)
      return autopilot.parameter(name)
    },
    calculatePercentage(value: number): number {
      return (value - MIN_PWM) / (MAX_PWM - MIN_PWM) * 100
    },
    updateParamValue(type: ParamType, newValue: number): void {
      const valueMap: ValueMap = {
        min: 'minValue',
        trim: 'trimValue',
        max: 'maxValue',
      }
      const paramMap: ParamMap = {
        min: 'min_param',
        trim: 'trim_param',
        max: 'max_param',
      }

      const valueKey = valueMap[type]
      const paramKey = paramMap[type]
      const param = this[paramKey] as Parameter | undefined

      if (newValue !== this[valueKey]) {
        this[valueKey] = Number(newValue)
        if (param) {
          param.value = this[valueKey]
        }
      }
    },
    initializeSliderValues(): void {
      if (this.min_param) {
        this.minValue = Number(this.min_param.value)
      }
      if (this.trim_param) {
        this.trimValue = Number(this.trim_param.value)
      }
      if (this.max_param) {
        this.maxValue = Number(this.max_param.value)
      }
    },
    getThumbPosition(index: number): number {
      const positions = [this.minPercent, this.trimPercent, this.maxPercent]
      return positions[index] ?? 0
    },
    getThumbValue(index: number): number {
      const values = [this.minValue, this.trimValue, this.maxValue]
      return values[index] ?? 0
    },
    startDragging(index: number): void {
      this.activeThumb = index
      this.isDragging = true
    },
    onSliderMouseDown(event: MouseEvent): void {
      const container = this.$refs.sliderContainer as HTMLElement
      if (!container) return

      const { value } = this.calculateValueFromEvent(event, container)
      const closestThumb = this.findClosestThumb(value)

      this.startDragging(closestThumb)
      this.updateThumbValue(event)
    },
    calculateValueFromEvent(event: MouseEvent | Touch, container: HTMLElement): { value: number } {
      const rect = container.getBoundingClientRect()
      const position = (event.clientX - rect.left) / rect.width
      return { value: Math.round(MIN_PWM + position * (MAX_PWM - MIN_PWM)) }
    },
    findClosestThumb(value: number): number {
      const distances = [
        Math.abs(value - this.minValue),
        this.trim_param ? Math.abs(value - this.trimValue) : Infinity,
        Math.abs(value - this.maxValue),
      ]
      return distances.indexOf(Math.min(...distances))
    },
    onSliderMouseMove(event: MouseEvent): void {
      if (this.isDragging) {
        this.updateThumbValue(event)
      }
    },
    onSliderMouseUp(): void {
      if (!this.isDragging) return

      const paramMap = {
        0: this.min_param,
        1: this.trim_param,
        2: this.max_param,
      }
      const valueMap = {
        0: this.minValue,
        1: this.trimValue,
        2: this.maxValue,
      }

      const param = paramMap[this.activeThumb as keyof typeof paramMap]
      const value = valueMap[this.activeThumb as keyof typeof valueMap]

      if (param) {
        mavlink2rest.setParam(
          param.name,
          value,
          autopilot.system_id,
          param.paramType.type,
        )
        param.value = value
      }

      this.isDragging = false
      this.activeThumb = -1
    },
    updateThumbValue(event: MouseEvent | Touch): void {
      if (!this.isDragging) return

      const container = this.$refs.sliderContainer as HTMLElement
      if (!container) return

      const { value } = this.calculateValueFromEvent(event, container)
      this.updateValueBasedOnThumb(value)
    },
    updateValueBasedOnThumb(value: number): void {
      const hasTrim = !!this.trim_param
      const constraints = {
        0: { min: MIN_PWM, max: hasTrim ? this.trimValue - 1 : this.maxValue - 1 },
        1: { min: this.minValue + 1, max: this.maxValue - 1 },
        2: { min: hasTrim ? this.trimValue + 1 : this.minValue + 1, max: MAX_PWM },
      }

      const updateFunctions = {
        0: this.updateMin,
        1: this.updateTrim,
        2: this.updateMax,
      }

      const constraint = constraints[this.activeThumb as keyof typeof constraints]
      const updateFunction = updateFunctions[this.activeThumb as keyof typeof updateFunctions]

      if (constraint && updateFunction) {
        const constrainedValue = Math.min(Math.max(constraint.min, value), constraint.max)
        updateFunction(constrainedValue.toString())
      }
    },
    updateMin(value: string): void {
      const maxConstraint = this.trim_param ? this.trimValue - 1 : this.maxValue - 1
      this.updateParamWithConstraints(value, this.min_param, MIN_PWM, maxConstraint, 'minValue')
    },
    updateTrim(value: string): void {
      this.updateParamWithConstraints(value, this.trim_param, this.minValue + 1, this.maxValue - 1, 'trimValue')
    },
    updateMax(value: string): void {
      const minConstraint = this.trim_param ? this.trimValue + 1 : this.minValue + 1
      this.updateParamWithConstraints(value, this.max_param, minConstraint, MAX_PWM, 'maxValue')
    },
    updateParamWithConstraints(
      value: string,
      param: Parameter | undefined,
      min: number,
      max: number,
      property: 'minValue' | 'trimValue' | 'maxValue',
    ): void {
      const numValue = Number(value)
      if (param && !Number.isNaN(numValue)) {
        this[property] = Math.min(Math.max(min, numValue), max)
        if (param.value !== this[property]) {
          param.value = this[property]
        }
      }
    },
    onTouchStart(event: TouchEvent): void {
      event.preventDefault()
      const touch = event.touches[0]
      this.onSliderMouseDown({
        clientX: touch.clientX,
        clientY: touch.clientY,
      } as MouseEvent)
    },
    onTouchMove(event: TouchEvent): void {
      event.preventDefault()
      const touch = event.touches[0]
      this.onSliderMouseMove({
        clientX: touch.clientX,
        clientY: touch.clientY,
      } as MouseEvent)
    },
    onTouchEnd(): void {
      this.onSliderMouseUp()
    },
  },
})
</script>

<style scoped>
.parameter-card {
  margin-bottom: 12px;
  padding: 10px;
  transition: box-shadow 0.2s;
}

.parameter-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
}

.parameter-card.disabled-card {
  opacity: 0.5;
  pointer-events: none;
}

.servo-slider {
  position: relative;
  height: 80px;
  cursor: pointer;
  padding: 0 10px;
  margin: 20px 0;
}

.slider-track {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 100%;
  height: 4px;
  background-color: rgba(128, 128, 128, 0.2);
  border-radius: 2px;
}

.slider-fill {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  height: 4px;
  background-color: var(--v-primary-base);
  border-radius: 2px;
  opacity: 0.8;
}

.slider-thumb {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 16px;
  height: 16px;
  background-color: var(--v-primary-base);
  border: 2px solid white;
  border-radius: 50%;
  cursor: grab;
  transition: all 0.2s ease;
  z-index: 1;
}

.slider-thumb:hover {
  transform: translate(-50%, -50%) scale(1.1);
  box-shadow: 0 0 0 8px rgba(var(--v-primary-base), 0.1);
}

.slider-thumb.active {
  transform: translate(-50%, -50%) scale(1.2);
  cursor: grabbing;
  box-shadow: 0 0 0 12px rgba(var(--v-primary-base), 0.15);
}

.thumb-label {
  position: absolute;
  top: -25px;
  left: 50%;
  transform: translateX(-50%);
  background-color: var(--v-primary-base);
  color: white;
  padding: 2px 4px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  user-select: none;
  text-align: center;
}
</style>
