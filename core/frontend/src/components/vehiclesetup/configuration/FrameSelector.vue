<template>
  <div class="frame-selector">
    <v-row>
      <v-col
        v-for="option in frameOptions"
        :key="option.value"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card
          :class="{ 'selected-frame': isSelected(option.value) }"
          @click="selectFrame(option.value)"
          class="frame-card"
          :elevation="isSelected(option.value) ? 4 : 1"
        >
          <model-viewer
            :src="getModelPath(option.value)"
            :alt="option.label"
            auto-rotate
            disable-zoom
            :style="{ width: '100%', height: '200px' }"
          ></model-viewer>
          <v-card-title class="text-center">
            {{ option.label }}
          </v-card-title>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script lang="ts">
import Vue from 'vue'
import Parameter from '@/types/autopilot/parameter'
import { vehicle_folder, frame_name } from '../viewers/modelHelper'
import autopilot from '@/store/autopilot_manager'

interface FrameParameter extends Parameter {
  values: { [key: string]: string }
}

export default Vue.extend({
  name: 'FrameSelector',
  props: {
    parameter: {
      type: Object as () => FrameParameter,
      required: true,
    },
  },
  data() {
    return {
      selectedValue: null as number | null,
    }
  },
  computed: {
    frameOptions() {
      if (!this.parameter?.options) return []
      return Object.entries(this.parameter.options).map(([value, label]) => ({
        value: parseInt(value),
        label: label as string,
      }))
    },
  },
  methods: {
    isSelected(value: number): boolean {
      return this.selectedValue === value
    },
    selectFrame(value: number) {
      this.selectedValue = value
      this.$emit('update:value', value)
    },
    getModelPath(frameValue: number): string {
      if (!autopilot.vehicle_type) return ''
      return `/assets/vehicles/models/${this.vehicleFolder()}/${this.frame_name(autopilot.vehicle_type, frameValue)}.glb`
    },
    vehicleFolder(): string {
      return vehicle_folder()
    },
    frame_name
  },
  mounted() {
    if (this.parameter.value !== undefined) {
      this.selectedValue = this.parameter.value
    }
  },
})
</script>

<style scoped>
.frame-selector {
  width: 100%;
}

.frame-card {
  cursor: pointer;
  transition: all 0.3s ease;
}

.frame-card:hover {
  transform: translateY(-5px);
}

.selected-frame {
  border: 2px solid var(--v-primary-base);
}

model-viewer {
  background-color: #f5f5f5;
  border-radius: 4px 4px 0 0;
}
</style> 