<template>
  <div>
    <model-viewer
      id="modelviewer"
      :src="src"
      auto-rotate
      camera-controls
      shadow-intensity="0.3"
      camera-orbit="45deg 65deg 1.2m"
      camera-target="-0.05m -0.03m 0m"
    >
      <button
        v-for="(item, index) in Object.values(displayedAnnotations)"
        :key="'annotation' + index"
        :slot="`hotspot-${index}`"
        type="button"
        class="Hotspot"
        :data-position="item.position"
        :data-normal="item.normal"
        data-visibility-attribute="visible"
      >
        <div class="HotspotAnnotation">
          {{ item.text }}
        </div>
      </button>
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

import bluerov from '@/assets/vehicles/models/bluerov.glb'
import autopilot_data from '@/store/autopilot'
import ping from '@/store/ping'
import { BTN_FUNCTION, FRAME_CONFIG, SERVO_FUNCTION } from '@/types/autopilot/parameter-sub-enums'
import { Dictionary } from '@/types/common'
import { PingType } from '@/types/ping'

const AllAnnotations = {
  Motor6heavy: {
    position: '0.10586189429698731m 0.0713389215292608m -0.21733868001562004m',
    normal: '0 1 0',
    text: 'Motor 6',
  },
  Motor5heavy: {
    position: '0.10578823301632309m 0.07133540921620643m 0.2167787642211954m',
    normal: '0 1 0',
    text: 'Motor 5',
  },
  Motor6standard: {
    position: '-0.005735193473105887m 0.09324964239559687m -0.10908695850046612m',
    normal: '0 1 0',
    text: 'Motor 6',
  },
  Motor5standard: {
    position: '-0.014944891051514142m 0.09296470070596237m 0.11045209178891321m',
    normal: '0 1 0',
    text: 'Motor 5',
  },
  Motor7heavy: {
    position: '-0.13428090736591214m 0.07133942670184504m 0.2164338103576852m',
    normal: '0 1 0',
    text: 'Motor 7',
  },
  Motor8heavy: {
    position: '-0.13346028414827638m 0.07134115867631283m -0.21678615277237565m',
    normal: '0 1 0',
    text: 'Motor 8',
  },
  Motor1: {
    position: '0.16237901231379895m -0.04480420421952533m 0.07717136042469966m',
    normal: '1 0 0',
    text: 'Motor 1',
  },
  Motor2: {
    position: '0.16239254215613144m -0.04414622495516646m -0.07747335058393973m',
    normal: '1 0 0',
    text: 'Motor 2',
  },
  Motor3: {
    position: '-0.20541099975383176m -0.04400868294373063m 0.07452124173999553m',
    normal: '-1 0 0',
    text: 'Motor 3',
  },
  Motor4: {
    position: '-0.20498456499943424m -0.0442730983355142m -0.07412432106505812m',
    normal: '-1 0 0',
    text: 'Motor 4',
  },
}

const standardSetup = {
  Motor1: AllAnnotations.Motor1,
  Motor2: AllAnnotations.Motor2,
  Motor3: AllAnnotations.Motor3,
  Motor4: AllAnnotations.Motor4,
  Motor5standard: AllAnnotations.Motor5standard,
  Motor6standard: AllAnnotations.Motor6standard,
}

const heavySetup = {
  Motor1: AllAnnotations.Motor1,
  Motor2: AllAnnotations.Motor2,
  Motor3: AllAnnotations.Motor3,
  Motor4: AllAnnotations.Motor4,
  Motor5heavy: AllAnnotations.Motor5heavy,
  Motor6heavy: AllAnnotations.Motor6heavy,
  Motor7heavy: AllAnnotations.Motor7heavy,
  Motor8heavy: AllAnnotations.Motor8heavy,
}

export default Vue.extend({
  name: 'BlueRovViewer',
  props: {
    highlight: {
      type: String,
      required: false,
      default: null,
    },
    noannotations: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      src: bluerov,
      displayedAnnotations: {} as Dictionary<{normal: string, position: string, text: string}>,
    }
  },
  computed: {
    frame_type() {
      return autopilot_data.parameter('FRAME_CONFIG')?.value
    },
    lights1_are_present() {
      const servo_params = autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
      return servo_params.some((parameter) => parameter.value === SERVO_FUNCTION.RCIN8)
    },
    lights2_are_present() {
      const servo_params = autopilot_data.parameterRegex('^SERVO(\\d+)_FUNCTION$')
      return servo_params.some((parameter) => parameter.value === SERVO_FUNCTION.RCIN9)
    },
    viewer() {
      return document.getElementById('modelviewer') as ModelViewerElement
    },
    gripper_is_present() {
      const mavlink = autopilot_data.parameter('GRIP_ENABLE')?.value === 1
      if (mavlink) {
        return true
      }

      // Checks for gripper by checking joystick functions
      const btn_params = autopilot_data.parameterRegex('^BTN(\\d+)_S?FUNCTION$')

      const functions = [
        BTN_FUNCTION.SERVO_1_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_1_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_2_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_2_MIN_MOMENTARY,
        BTN_FUNCTION.SERVO_3_MAX_MOMENTARY,
        BTN_FUNCTION.SERVO_3_MIN_MOMENTARY,
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
      // Deals with changing the highlighed part of the model when the "highlight" prop changes
      if (!highlight) {
        this.redraw()
        const frameAnnotations = this.isHeavy() ? heavySetup : standardSetup
        const annotations = this.noannotations ? {} : frameAnnotations
        Vue.set(this, 'displayedAnnotations', annotations)
        this.forceRefreshAnnotations()
        return
      }
      this.setAlphas(0.05)
      this.makeOpaque(this.highlight)
      const frameAnnotations = this.isHeavy() ? heavySetup : standardSetup
      const annotations = this.noannotations ? {} : frameAnnotations
      this.hideIrrelevantParts()
      Vue.set(this, 'displayedAnnotations', Object.fromEntries(
        Object.entries(annotations).filter(([key, _value]) => key.startsWith(this.highlight)),
      ))
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
  mounted() {
    this.viewer.addEventListener(
      'load',
      () => {
        this.hideIrrelevantParts()
        this.forceRefreshAnnotations()
      },
    )
  },
  methods: {
    redraw() {
      this.setAlphas(1.0)
      this.hideIrrelevantParts()
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
    hideIrrelevantParts(): void {
      if (!this.gripper_is_present) {
        this.setAlphas(0.0, 'gripper')
      }
      if (!this.lights1_are_present) {
        this.setAlphas(0.0, 'lights 1')
      }
      if (!this.lights2_are_present) {
        this.setAlphas(0.0, 'lights 2')
      }
      if (!this.ping1D_is_present) {
        this.setAlphas(0.0, 'ping1d')
      }
      if (!this.ping360_is_present) {
        this.setAlphas(0.0, 'ping360')
      }
      if (!this.isHeavy()) {
        this.setAlphas(0.0, 'heavy')
        if (!this.noannotations) {
          Vue.set(this, 'displayedAnnotations', standardSetup)
        }
      } else {
        this.setAlphas(0.0, 'standard')
        if (!this.noannotations) {
          Vue.set(this, 'displayedAnnotations', heavySetup)
        }
      }
    },
    forceRefreshAnnotations() {
      if (this.noannotations) {
        Vue.set(this, 'displayedAnnotations', [])
        return
      }
      for (const [index, annotation] of Object.values(this.displayedAnnotations).entries()) {
        this.viewer.updateHotspot({
          name: `hotspot-${index}`,
          position: annotation.position,
        })
      }
    },
    isHeavy() {
      return this.frame_type === FRAME_CONFIG.VECTORED_6DOF
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
