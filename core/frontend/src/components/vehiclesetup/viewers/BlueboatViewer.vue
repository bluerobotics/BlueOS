<template>
  <div>
    <model-viewer
      id="modelviewer"
      :src="src"
      auto-rotate
      camera-controls
      shadow-intensity="0.3"
      camera-orbit="45deg 65deg 1.9m"
      camera-target="-0.05m 0.3m 0m"
    >
      <div
        slot="progress-bar"
        class="progress-bar hide"
      >
        <div class="update-bar" />
      </div>
    </model-viewer>
  </div>
</template>

<script lang="ts">

import '@google/model-viewer/dist/model-viewer'

import { ModelViewerElement } from '@google/model-viewer/lib/model-viewer'
import Vue from 'vue'

import blueboat from '@/assets/vehicles/models/boat.glb'
import autopilot_data from '@/store/autopilot'

export default Vue.extend({
  name: 'BlueRovViewer',
  props: {
    highlight: {
      type: String,
      required: false,
      default: null,
    },
  },
  data() {
    return {
      src: blueboat,
    }
  },
  computed: {
    frame_type() {
      return autopilot_data.parameter('FRAME_CONFIG')?.value
    },
    viewer() {
      return document.getElementById('modelviewer') as ModelViewerElement
    },
  },
  watch: {
    highlight(highlight: string | null): void {
      // Deals with changing the highlighed part of the model when the "highlight" prop changes
      if (!highlight) {
        this.redraw()
        return
      }
      this.setAlphas(0.05)
      this.makeOpaque(this.highlight)
    },
    frame_type() {
      this.redraw()
    },
  },
  methods: {
    redraw() {
      this.setAlphas(1.0)
    },
    setAlphas(new_color: number, text = ''): void {
      const lower_text = text.toLowerCase()
      const materials = this.viewer?.model?.materials ?? []
      const affected_materials = materials.filter(
        (material) => material.name.toLowerCase().includes(lower_text),
      )
      for (const material of affected_materials) {
        material.setAlphaMode(new_color < 1.0 ? 'BLEND' : 'OPAQUE')
        const color = material.pbrMetallicRoughness.baseColorFactor
        color[3] = new_color
        material.pbrMetallicRoughness.setBaseColorFactor(color)
      }
    },
    makeOpaque(part: string) {
      this.setAlphas(1.0, part)
    },
  },
})
</script>

<style scoped>
model-viewer {
  min-height: 500px;
  width: 100%;
}

.HotspotAnnotation {
    background: rgb(255, 255, 255);
    border-radius: 4px;
    box-shadow: rgb(0 0 0 / 25%) 0px 2px 4px;
    color: rgba(0, 0, 0, 0.8);
    display: block;
    font-family: Futura, "Helvetica Neue", sans-serif;
    font-size: 16px;
    font-weight: 700;
    left: calc(100% + 1em);
    max-width: 128px;
    overflow-wrap: break-word;
    padding: 0.5em 1em;
    position: absolute;
    top: 50%;
    width: max-content;
}

.Hotspot:not([data-visible]) > * {
    opacity: 0;
    pointer-events: none;
    transform: translateY(calc(-50% + 4px));
    transition: transform 0.3s ease 0s, opacity 0.3s ease 0s;
}

.Hotspot {
    background: rgb(255, 255, 255);
    border-radius: 32px;
    border: 0px;
    box-shadow: rgba(0, 0, 0, 0.25) 0px 2px 4px;
    box-sizing: border-box;
    cursor: pointer;
    height: 24px;
    padding: 8px;
    position: relative;
    transition: opacity 0.3s ease 0s;
    width: 24px;
}
</style>
