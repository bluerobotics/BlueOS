<template>
  <div class="frame-selector">
    <v-row v-if="parameter?.options">
      <v-col
        v-for="option in displayOptions"
        :key="option.value"
        cols="12"
        :sm="!isExpanded ? '12' : '6'"
        :md="!isExpanded ? '12' : '4'"
        :lg="!isExpanded ? '12' : '3'"
      >
        <v-card
          :class="{ 'selected-frame': isSelected(option.value) }"
          class="frame-card"
          :elevation="isSelected(option.value) ? 4 : 1"
          @click="handleFrameClick(option.value)"
        >
          <generic-viewer
            :modelpath="getModelPath(option.value)"
            :autorotate="true"
            :disable-zoom="true"
            :noannotations="true"
            :transparent="true"
            :cameracontrols="false"
            :style="{ width: '100%', height: !isExpanded ? '300px' : '250px' }"
            :highlight="['Motor', 'Throttle']"
            :camera-orbit="isSelected(option.value) ? '-45deg 65deg 1.4m' : '-45deg 55deg 1.4m'"
          />
          <v-card-title class="text-center">
            {{ option.label }}
          </v-card-title>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script lang="ts">
import Vue, { PropType } from 'vue'

import autopilot from '@/store/autopilot_manager'
import Parameter from '@/types/autopilot/parameter'

import { frame_name, vehicle_folder } from '../viewers/modelHelper'

export default Vue.extend({
  name: 'FrameSelector',
  props: {
    parameter: {
      type: Object as PropType<Parameter | undefined>,
      required: true,
    },
  },
  data() {
    return {
      selectedValue: null as number | null,
      isExpanded: false,
    }
  },
  computed: {
    frameOptions(): Array<{ value: number; label: string }> {
      if (!this.parameter?.options) return []
      return Object.entries(this.parameter.options).map(([value, label]) => ({
        value: parseInt(value, 10),
        label: label as string,
      }))
    },
    displayOptions(): Array<{ value: number; label: string }> {
      if (!this.isExpanded && this.selectedValue !== null) {
        return this.frameOptions.filter(
          (option: { value: number; label: string }) => option.value === this.selectedValue,
        )
      }
      return this.frameOptions
    },
  },
  mounted() {
    if (this.parameter?.value !== undefined) {
      this.selectedValue = this.parameter.value
      this.isExpanded = false
    }
  },
  methods: {
    isSelected(value: number): boolean {
      return this.selectedValue === value
    },
    handleFrameClick(value: number) {
      if (this.selectedValue === value) {
        this.isExpanded = !this.isExpanded
      } else {
        this.selectedValue = value
        this.isExpanded = false
        this.$emit('update:value', value)
      }
    },
    getModelPath(frameValue: number): string {
      if (!autopilot.vehicle_type) return ''
      const frameName = this.frame_name(autopilot.vehicle_type, frameValue)
      return `/assets/vehicles/models/${this.vehicleFolder()}/${frameName?.toUpperCase()}.glb`
    },
    vehicleFolder(): string {
      return vehicle_folder()
    },
    frame_name,
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
  margin-bottom: 16px;
}

.frame-card:hover {
  transform: translateY(-5px);
}

.selected-frame {
  border: 2px solid var(--v-primary-base);
  max-width: 500px;
  margin: 0 auto;
}

model-viewer {
  background-color: #f5f5f5;
  border-radius: 4px 4px 0 0;
}
</style>
