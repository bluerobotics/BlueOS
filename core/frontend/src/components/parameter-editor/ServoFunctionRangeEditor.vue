<template>
  <div>
    <v-card class="mt-4 mb-4">
      <v-card-text>
        <div class="d-flex align-center mb-4">
          <span class="text-h6">{{ title }}</span>
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
            <span>{{ tooltip }}</span>
          </v-tooltip>
        </div>
        <div
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
            v-show="thumbType !== 'trim' || trimParam"
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
              :label="resolvedMinParam?.name"
              :param="resolvedMinParam"
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
          :disabled="!trimParam"
          :class="{ 'disabled-card': !trimParam }"
        >
          <v-card-text class="py-2">
            <inline-parameter-editor
              :auto-set="true"
              :label="resolvedTrimParam?.name ?? 'Trim'"
              :param="resolvedTrimParam"
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
              :label="resolvedMaxParam?.name"
              :param="resolvedMaxParam"
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

export default Vue.extend({
  name: 'ServoFunctionRangeEditor',
  components: {
    InlineParameterEditor,
  },
  props: {
    param: {
      type: Object as () => Parameter,
      required: true,
    },
    minParam: {
      type: Object as () => Parameter | undefined,
      default: undefined,
    },
    trimParam: {
      type: Object as () => Parameter | undefined,
      default: undefined,
    },
    maxParam: {
      type: Object as () => Parameter | undefined,
      default: undefined,
    },
    title: {
      type: String,
      default: 'Servo Range Configuration',
    },
    tooltip: {
      type: String,
      default: 'Adjust the minimum, trim, and maximum PWM values for this servo',
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
    resolvedTrimParam(): Parameter | undefined {
      return this.trimParam ?? this.getParamByType('_TRIM')
    },
    resolvedMaxParam(): Parameter | undefined {
      return this.maxParam ?? this.getParamByType('_MAX')
    },
    resolvedMinParam(): Parameter | undefined {
      return this.minParam ?? this.getParamByType('_MIN')
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
    minParam: {
      handler() {
        this.initializeSliderValues()
      },
    },
    trimParam: {
      handler() {
        this.initializeSliderValues()
      },
    },
    maxParam: {
      handler() {
        this.initializeSliderValues()
      },
    },
    'resolvedMinParam.value': function onMinParamChange(newValue: number) {
      this.updateParamValue('min', newValue)
    },
    'resolvedTrimParam.value': function onTrimParamChange(newValue: number) {
      this.updateParamValue('trim', newValue)
    },
    'resolvedMaxParam.value': function onMaxParamChange(newValue: number) {
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
        min: 'resolvedMinParam',
        trim: 'resolvedTrimParam',
        max: 'resolvedMaxParam',
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
      if (this.resolvedMinParam) {
        this.minValue = Number(this.resolvedMinParam.value)
      }
      if (this.resolvedTrimParam) {
        this.trimValue = Number(this.resolvedTrimParam.value)
      }
      if (this.resolvedMaxParam) {
        this.maxValue = Number(this.resolvedMaxParam.value)
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
        this.resolvedTrimParam ? Math.abs(value - this.trimValue) : Infinity,
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
        0: this.resolvedMinParam,
        1: this.resolvedTrimParam,
        2: this.resolvedMaxParam,
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
      const hasTrim = !!this.resolvedTrimParam
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
      const maxConstraint = this.resolvedTrimParam ? this.trimValue - 1 : this.maxValue - 1
      this.updateParamWithConstraints(value, this.resolvedMinParam, MIN_PWM, maxConstraint, 'minValue')
    },
    updateTrim(value: string): void {
      this.updateParamWithConstraints(
        value,
        this.resolvedTrimParam,
        this.minValue + 1,
        this.maxValue - 1,
        'trimValue',
      )
    },
    updateMax(value: string): void {
      const minConstraint = this.resolvedTrimParam ? this.trimValue + 1 : this.minValue + 1
      this.updateParamWithConstraints(value, this.resolvedMaxParam, minConstraint, MAX_PWM, 'maxValue')
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
