<template>
  <div class="frame-selector">
    <v-row v-if="parameter?.options">
      <v-col
        v-for="option in displayOptions"
        :key="option.value"
        cols="12"
        :sm="isCollapsed ? '12' : '6'"
        :md="isCollapsed ? '12' : '4'"
        :lg="isCollapsed ? '12' : '3'"
      >
        <v-card
          :class="{ 'selected-frame': isSelected(option.value) }"
          @click="selectFrame(option.value)"
          class="frame-card"
          :elevation="isSelected(option.value) ? 4 : 1"
        >
          <generic-viewer
            :modelpath="getModelPath(option.value)"
            :autorotate="true"
            :disable-zoom="true"
            :noannotations="true"
            :transparent="true"
            :cameracontrols="false"
            :style="{ width: '100%', height: isCollapsed ? '300px' : '200px' }"
            :highlight="['Motor']"
            :zoom="1.5"
            :camera_orbit="'-45deg 55deg 0.8m'"
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
import Parameter from '@/types/autopilot/parameter'
import { vehicle_folder, frame_name } from '../viewers/modelHelper'
import autopilot from '@/store/autopilot_manager'

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
      isCollapsed: false,
    }
  },
  computed: {
    frameOptions(): Array<{ value: number; label: string }> {
      if (!this.parameter?.options) return []
      return Object.entries(this.parameter.options).map(([value, label]) => ({
        value: parseInt(value),
        label: label as string,
      }))
    },
    displayOptions(): Array<{ value: number; label: string }> {
      if (this.isCollapsed && this.selectedValue !== null) {
        return this.frameOptions.filter((option: { value: number; label: string }) => option.value === this.selectedValue)
      }
      return this.frameOptions
    },
  },
  methods: {
    isSelected(value: number): boolean {
      return this.selectedValue === value
    },
    selectFrame(value: number) {
      if (this.selectedValue === value) {
        this.isCollapsed = false
      } else {
        this.selectedValue = value
        this.isCollapsed = true
        this.$emit('update:value', value)
      }
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
    if (this.parameter?.value !== undefined) {
      this.selectedValue = this.parameter.value
      this.isCollapsed = true
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
  margin-bottom: 16px;
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