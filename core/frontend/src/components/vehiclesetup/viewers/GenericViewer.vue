<template>
  <div>
    <model-viewer
      v-if="model_viewer_supported && model_viewer_ready && computed_model_path"
      id="modelviewer"
      ref="modelviewer"
      :src="model_override_path || computed_model_path"
      :auto-rotate="autorotate"
      :camera-controls="cameracontrols"
      :orientation="orientation"
      shadow-intensity="0.3"
      interaction-prompt="none"
      :camera-orbit="cameraOrbit"
      camera-target="auto 0m auto"
      @load="onModelViewerLoad"
    >
      <button
        v-for="annotation in filtered_annotations"
        :key="'annotation' + annotation.index"
        :slot="`hotspot-${annotation.index}`"
        class="Hotspot"
        type="button"
        :data-position="annotation.position ?? undefined"
        :data-normal="annotation.normal ?? undefined"
        :data-surface="annotation.surface ?? undefined"
        data-visibility-attribute="visible"
      >
        <div class="HotspotAnnotation">
          {{ annotation.text }}
        </div>
      </button>
      <div
        slot="progress-bar"
        class="progress-bar hide"
      >
        <div class="update-bar" />
      </div>

      <v-btn
        id="image-download-btn"
        class="mt-6 mb-1"
        elevation="1"
        fab
        x-small
        @click="download"
      >
        <v-icon>
          mdi-camera
        </v-icon>
      </v-btn>
    </model-viewer>
    <div
      v-else-if="!model_viewer_supported"
      class="d-flex flex-column align-center text-center pa-4"
    >
      <v-icon
        style="height: 170px"
        size="200"
        v-text="'mdi-cube-off-outline'"
      />
      <p class="text-h6 ma-2">
        3D viewer unavailable
      </p>
      <p class="text-body-2" style="max-width: 350px">
        This browser does not support the required WebGL features.
      </p>
    </div>
    <div v-else-if="!show_model_not_found" class="d-flex flex-column align-center">
      <SpinningLogo size="30%" />
    </div>
    <div v-else class="d-flex flex-column align-center">
      <v-icon
        style="height: 170px"
        size="200"
        v-text="'mdi-sail-boat-sink'"
      />
      <p class="text-h6 ma-2">
        Vehicle model not found
      </p>
      <p class="text-center text-body-2" style="max-width: 350px">
        If you want to add a custom 3D model please follow the instructions in
        <a
          href="https://blueos.cloud/docs/latest/usage/advanced/#vehicle-model"
          target="_blank"
          class="text-decoration-none"
        >
          BlueOS Documentation
        </a>
      </p>
    </div>
  </div>
</template>

<script lang="ts">
import type { ModelViewerElement } from '@google/model-viewer/lib/model-viewer'
import type { HotspotConfiguration } from '@google/model-viewer/lib/three-components/Hotspot'
import axios from 'axios'
import { saveAs } from 'file-saver'
import Image from 'image-js'
import Vue from 'vue'

import SpinningLogo from '@/components/common/SpinningLogo.vue'
import autopilot_data from '@/store/autopilot'
import ping from '@/store/ping'
import {
  BTN_FUNCTION as SUB_BTN_FUNCTION,
  SERVO_FUNCTION as SUB_SERVO_FUNCTION,
} from '@/types/autopilot/parameter-sub-enums'
import { Dictionary, Indexed, Keyed } from '@/types/common'
import { PingType } from '@/types/ping'
import { canUseModelViewer, ensureModelViewer } from '@/utils/model_viewer_support'

import { checkModelOverrides, frame_name, vehicle_folder } from './modelHelper'

const MODEL_VIEWER_SUPPORTED = canUseModelViewer()

const models: Record<string, string> = import.meta.glob('/public/assets/vehicles/models/**', { eager: true })

export default Vue.extend({
  name: 'GenericViewer',
  components: { SpinningLogo },
  props: {
    cameracontrols: {
      type: Boolean,
      required: false,
      default: true,
    },
    orientation: {
      type: String,
      required: false,
      default: '0deg 0deg 0deg',
    },
    transparent: {
      type: Boolean,
      required: false,
      default: false,
    },
    highlight: {
      type: Array<string>,
      required: false,
      default: () => [],
    },
    autorotate: {
      type: Boolean,
      required: true,
    },
    noannotations: {
      type: Boolean,
      required: false,
      default: false,
    },
    modelpath: {
      type: String,
      required: false,
      default: undefined,
    },
    cameraOrbit: {
      type: String,
      required: false,
      default: '45deg 70deg 0deg',
    },
  },
  data() {
    return {
      model_override_path: '' as string | undefined,
      annotations: {} as Dictionary<HotspotConfiguration>,
      override_annotations: {} as Dictionary<HotspotConfiguration>,
      default_alphas: {} as Dictionary<number>,
      show_model_not_found: false,
      model_viewer_supported: MODEL_VIEWER_SUPPORTED,
      model_viewer_ready: false,
    }
  },
  computed: {
    computed_model_path(): string | undefined {
      if (this.modelpath) {
        return this.modelpath
      }
      return autopilot_data.vehicle_model
    },
    filtered_annotations(): (HotspotConfiguration & Indexed & Keyed)[] {
      if (this.noannotations) {
        return []
      }
      if (frame_name === undefined) {
        return []
      }
      // pick correct set
      let all = this.annotations
      // we meed to "probe" for Motor1 as the objects are always valid
      if ('Motor1' in this.override_annotations) {
        all = this.override_annotations
      }
      const keyed_indexed_annotations: (HotspotConfiguration & Indexed & Keyed)[] = []
      let index = 0
      for (const [key, hotspot] of Object.entries(all)) {
        keyed_indexed_annotations.push({
          ...hotspot,
          key,
          index,
        })
        index += 1
      }
      if (this.highlight) {
        return keyed_indexed_annotations.filter(
          (annotation) => this.highlight.some((highlight) => annotation.key.startsWith(highlight)),
        )
      }
      return keyed_indexed_annotations
    },
    lights1_are_present() {
      const servo_params = autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
      return servo_params.some((parameter) => parameter.value === SUB_SERVO_FUNCTION.RCIN9)
    },
    lights2_are_present() {
      const servo_params = autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
      return servo_params.some((parameter) => parameter.value === SUB_SERVO_FUNCTION.RCIN10)
    },
    gripper_is_present() {
      const mavlink = autopilot_data.parameter('GRIP_ENABLE')?.value === 1
      if (mavlink) {
        return true
      }
      // Checks for gripper by checking joystick functions
      const btn_params = autopilot_data.parameterRegex('^BTN(\\d+)_S?FUNCTION$')
      const functions = [
        SUB_BTN_FUNCTION.SERVO_1_MAX_MOMENTARY,
        SUB_BTN_FUNCTION.SERVO_1_MIN_MOMENTARY,
        SUB_BTN_FUNCTION.SERVO_2_MAX_MOMENTARY,
        SUB_BTN_FUNCTION.SERVO_2_MIN_MOMENTARY,
        SUB_BTN_FUNCTION.SERVO_3_MAX_MOMENTARY,
        SUB_BTN_FUNCTION.SERVO_3_MIN_MOMENTARY,
      ]
      for (const param of btn_params) {
        if (functions.includes(param.value)) {
          return true
        }
      }
      return false
    },
    ping1D_is_present() {
      return ping.available_ping_devices.some((device) => device.ping_type === PingType.Ping1D)
    },
    ping360_is_present() {
      return ping.available_ping_devices.some((device) => device.ping_type === PingType.Ping360)
    },
  },
  watch: {
    highlight(highlight: string | null): void {
      // Deals with changing the highlighted part of the model when the "highlight" prop changes
      if (!highlight) {
        this.redraw()
        this.forceRefreshAnnotations()
        return
      }
      this.redraw()
      this.hideIrrelevantParts()
      this.forceRefreshAnnotations()
    },
    async computed_model_path() {
      this.reloadAnnotations()
      this.model_override_path = await checkModelOverrides()
      this.override_annotations = await this.loadAnnotationsOverride()
      this.forceRefreshAnnotations()
    },
    frame_type() {
      this.redraw()
    },
    gripper_is_present() {
      this.redraw()
    },
    ping1D_is_present() {
      this.redraw()
    },
    ping360_is_present() {
      this.redraw()
    },
    lights1_are_present() {
      this.redraw()
    },
    lights2_are_present() {
      this.redraw()
    },
  },
  async mounted() {
    if (this.model_viewer_supported) {
      const loaded = await ensureModelViewer()
      this.model_viewer_ready = loaded
      this.model_viewer_supported = loaded
    }
    setTimeout(() => {
      if (!this.computed_model_path) {
        this.show_model_not_found = true
      }
    }, 5000)

    this.model_override_path = await checkModelOverrides()
    this.override_annotations = await this.loadAnnotationsOverride()
    this.reloadAnnotations()
  },
  methods: {
    onModelViewerLoad() {
      this.redraw()
      this.hideIrrelevantParts()
    },
    async download() {
      const viewer = this.$refs.modelviewer as ModelViewerElement
      const mimeType = 'image/png'
      const blob = await viewer.toBlob({ mimeType, idealAspect: true })
      const image = await Image.load(new Uint8Array(await blob.arrayBuffer()))

      // Find the bounding box of the non-zero pixels in the mask
      let xMin = image.width
      let yMin = image.height
      let xMax = 0
      let yMax = 0

      for (let y = 0; y < image.height; y += 1) {
        for (let x = 0; x < image.width; x += 1) {
          const pixel = image.getPixelXY(x, y)
          if (pixel[0] > 0) {
            xMin = Math.min(xMin, x)
            yMin = Math.min(yMin, y)
            xMax = Math.max(xMax, x)
            yMax = Math.max(yMax, y)
          }
        }
      }

      // Crop the image to the bounding box
      const cropped_image = image.crop({
        x: xMin,
        y: yMin,
        width: xMax - xMin + 1,
        height: yMax - yMin + 1,
      })

      // Save the image
      const file = new File([await cropped_image.toBlob(mimeType)], 'viewer.png', { type: mimeType })
      saveAs(file)
    },
    async reloadAnnotations() {
      const path = `/public/assets/vehicles/models/${vehicle_folder()}/${frame_name()}.json`
      const json = await models[path]
      if (json) {
        this.annotations = json.annotations ?? {}
      }
    },
    redraw() {
      if (this.transparent) {
        this.setAlphas(0.05)
        for (const part of this.highlight) {
          this.makeOpaque(part)
        }
      } else {
        this.setAlphas(1)
      }
      this.hideIrrelevantParts()
      this.forceRefreshAnnotations()
    },

    async loadAnnotationsOverride(): Promise<Dictionary<HotspotConfiguration>> {
      if (!this.model_override_path) {
        return {}
      }
      const candidate_path = this.model_override_path?.replace('glb', 'json')
      const response = await axios.get(candidate_path)
      return response.data?.annotations ?? {}
    },
    setAlphas(new_color: number, text = ''): void {
      const lower_text = text.toLowerCase()
      if (!this.$refs.modelviewer) {
        return
      }
      // eslint-disable-next-line no-extra-parens
      const materials = (this.$refs.modelviewer as ModelViewerElement).model?.materials ?? []
      const affected_materials = materials.filter((material) => material.name.toLowerCase().includes(lower_text))
      for (const material of affected_materials) {
        // store default alphas and do not allow going above it.
        if (!(material.name in this.default_alphas)) {
          // eslint-disable-next-line prefer-destructuring
          this.default_alphas[material.name] = material.pbrMetallicRoughness.baseColorFactor[3]
        }
        const color = material.pbrMetallicRoughness.baseColorFactor
        color[3] = Math.min(new_color, this.default_alphas[material.name])
        material.setAlphaMode(color[3] < 1.0 ? 'BLEND' : 'OPAQUE')
        material.pbrMetallicRoughness.setBaseColorFactor(color)
      }
    },
    hideIrrelevantParts(): void {
      if (!this.gripper_is_present) {
        this.setAlphas(0, 'gripper')
      }
      if (!this.lights1_are_present) {
        this.setAlphas(0, 'lights 1')
      }
      if (!this.lights2_are_present) {
        this.setAlphas(0, 'lights 2')
      }
      if (!this.ping1D_is_present) {
        this.setAlphas(0, 'ping1d')
      }
      if (!this.ping360_is_present) {
        this.setAlphas(0, 'ping360')
      }
    },
    makeOpaque(part: string) {
      this.setAlphas(1, part)
    },
    forceRefreshAnnotations() {
      if (this.noannotations) {
        return
      }
      for (const annotation of this.filtered_annotations) {
        if (annotation.position) {
          // eslint-disable-next-line no-extra-parens
          (this.$refs.modelviewer as ModelViewerElement)?.updateHotspot({
            name: `hotspot-${annotation.index}`,
            position: annotation.position,
            normal: annotation.normal,
            surface: undefined,
          } as HotspotConfiguration)
        } else {
          // eslint-disable-next-line no-extra-parens
          (this.$refs.modelviewer as ModelViewerElement).updateHotspot({
            name: `hotspot-${annotation.index}`,
            position: undefined,
            normal: undefined,
            surface: annotation.surface,
          } as HotspotConfiguration)
        }
      }
    },
  },
})
</script>

<style scoped>
model-viewer {
  height: 100%;
  width: 100%;
}
.HotspotAnnotation {
    background: rgb(255, 255, 255);
    border-radius: 4px;
    box-shadow: rgb(0 0 0 / 25%) 0 2px 4px;
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
    border: 0;
    box-shadow: rgba(0, 0, 0, 0.25) 0 2px 4px;
    box-sizing: border-box;
    cursor: pointer;
    height: 24px;
    padding: 8px;
    position: relative;
    transition: opacity 0.3s ease 0s;
    width: 24px;
}

#image-download-btn {
    display: none;
    position: absolute;
    right: 15px;
    bottom: 0;
}

#modelviewer:hover #image-download-btn {
    display: inline-flex !important;
}
</style>
