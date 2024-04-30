<template>
  <div v-if="parameter">
    <v-card outline class="pa-5 mt-4 mr-2 mb-2">
      <v-card-title>Board Orientation</v-card-title>
      <div class="threejs-relative-container">
        <v-card class="orientation-selector-overlay">
          <parameter-label :param="parameter" label="AHRS_ORIENTATION" />
          <v-select
            v-model="selectedRotation"
            :items="rotationsWithCustom"
            return-object
            :item-text="'name'"
            @blur="handleRotationLeave"
          >
            <template #item="{ item, on, attrs }">
              <v-list-item
                v-bind="attrs"
                v-on="on"
                @mouseover="handleRotationHover(item)"
              >
                <v-list-item-content>
                  <v-list-item-title>{{ item.name }}</v-list-item-title>
                </v-list-item-content>
              </v-list-item>
            </template>
          </v-select>
        </v-card>
        <div class="threejs-container">
          <div ref="threemount" class="threejsmount" />
        </div>
      </div>
    </v-card>
  </div>
</template>

<script lang="ts">
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader'
import { GLTF, GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { PropType } from 'vue'

import { get_board_model } from '@/components/vehiclesetup/viewers/modelHelper'
import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'

// Import DRACO decoder files using Vite's glob import
const dracoFiles = import.meta.glob('/node_modules/three/examples/jsm/libs/draco/*', { eager: true, as: 'url' })

class Rotation {
  name: string

  roll: number

  pitch: number

  yaw: number

  rotationNumber: number

  constructor(name: string, roll: number, pitch: number, yaw: number, rotationNumber: number) {
    this.name = name
    this.roll = roll
    this.pitch = pitch
    this.yaw = yaw
    this.rotationNumber = rotationNumber
  }
}

export default {
  name: 'OrientationPicker',
  props: {
    parameter: {
      type: Object as PropType<Parameter | undefined>,
      required: false,
      default: undefined,
    },
    componentModel: {
      type: String,
      required: false,
      default: undefined,
    },
  },
  data() {
    return {
      hoveredRotation: undefined as Rotation | undefined,
      rotations: [
        new Rotation('None', 0, 0, 0, 0),
        new Rotation('Yaw45', 0, 0, 45, 1),
        new Rotation('Yaw90', 0, 0, 90, 2),
        new Rotation('Yaw135', 0, 0, 135, 3),
        new Rotation('Yaw180', 0, 0, 180, 4),
        new Rotation('Yaw225', 0, 0, 225, 5),
        new Rotation('Yaw270', 0, 0, 270, 6),
        new Rotation('Yaw315', 0, 0, 315, 7),
        new Rotation('Roll180', 180, 0, 0, 8),
        new Rotation('Yaw45Roll180', 180, 0, 45, 9),
        new Rotation('Yaw90Roll180', 180, 0, 90, 10),
        new Rotation('Yaw135Roll180', 180, 0, 135, 11),
        new Rotation('Pitch180', 0, 180, 0, 12),
        new Rotation('Yaw225Roll180', 180, 0, 225, 13),
        new Rotation('Yaw270Roll180', 180, 0, 270, 14),
        new Rotation('Yaw315Roll180', 180, 0, 315, 15),
        new Rotation('Roll90', 90, 0, 0, 16),
        new Rotation('Yaw45Roll90', 90, 0, 45, 17),
        new Rotation('Yaw90Roll90', 90, 0, 90, 18),
        new Rotation('Yaw135Roll90', 90, 0, 135, 19),
        new Rotation('Roll270', 270, 0, 0, 20),
        new Rotation('Yaw45Roll270', 270, 0, 45, 21),
        new Rotation('Yaw90Roll270', 270, 0, 90, 22),
        new Rotation('Yaw135Roll270', 270, 0, 135, 23),
        new Rotation('Pitch90', 0, 90, 0, 24),
        new Rotation('Pitch270', 0, 270, 0, 25),
        new Rotation('Yaw90Pitch180', 0, 180, 90, 26),
        new Rotation('Yaw270Pitch180', 0, 180, 270, 27),
        new Rotation('Pitch90Roll90', 90, 90, 0, 28),
        new Rotation('Pitch90Roll180', 180, 90, 0, 29),
        new Rotation('Pitch90Roll270', 270, 90, 0, 30),
        new Rotation('Pitch180Roll90', 90, 180, 0, 31),
        new Rotation('Pitch180Roll270', 270, 180, 0, 32),
        new Rotation('Pitch270Roll90', 90, 270, 0, 33),
        new Rotation('Pitch270Roll180', 180, 270, 0, 34),
        new Rotation('Pitch270Roll270', 270, 270, 0, 35),
        new Rotation('Yaw90Pitch180Roll90', 90, 180, 90, 36),
        new Rotation('Yaw270Roll90', 90, 0, 270, 37),
        new Rotation('Yaw293Pitch68Roll180', 180, 68, 293, 38),
        new Rotation('Pitch315', 0, 315, 0, 39),
        new Rotation('Pitch315Roll90', 90, 315, 0, 40),
        new Rotation('Pitch7', 0, 7, 0, 41),
        new Rotation('Roll45', 45, 0, 0, 42),
        new Rotation('Roll315', 315, 0, 0, 43),
      ] as Rotation[],
      unsupportedRotation: new Rotation('UNSUPPORTED', 0, 0, 0, -1),
      object: undefined as THREE.Object3D | undefined,
      camera: undefined as THREE.Camera | undefined,
      scene: undefined as THREE.Scene | undefined,
      renderer: undefined as THREE.WebGLRenderer | undefined,
      vehicle_obj: undefined as THREE.Object3D | undefined,
      arrows: [] as THREE.ArrowHelper[],
      orbitControls: undefined as OrbitControls | undefined,
    }
  },
  computed: {
    threejs_canvas(): HTMLDivElement {
      return this.$refs.threemount as HTMLDivElement
    },
    vehicle_model(): string | undefined {
      return autopilot_data.vehicle_model
    },
    rotationsWithCustom(): Rotation[] {
      if (this.isUnsupportedRotation) {
        return [this.getUnsupportedRotation(), ...this.rotations]
      }
      return [...this.rotations].sort((a, b) => a.name.localeCompare(b.name))
    },
    isUnsupportedRotation(): boolean {
      if (!this.parameter || this.parameter.value === undefined) {
        return false
      }

      const paramValue = Number(this.parameter.value)
      return !this.rotations.some((rotation) => rotation.rotationNumber === paramValue)
    },
    selectedRotation: {
      get(): Rotation | undefined {
        if (!this.parameter || this.parameter.value === undefined) {
          return undefined
        }

        const paramValue = Number(this.parameter.value)
        const matchingRotation = this.rotations.find((rotation) => rotation.rotationNumber === paramValue)

        if (!matchingRotation) {
          console.log(`Rotation ${paramValue} is not supported`)
          return this.getUnsupportedRotation()
        }

        return matchingRotation
      },
      set(newValue: Rotation) {
        if (this.parameter === undefined) {
          return
        }
        mavlink2rest.setParam(
          this.parameter.name,
          newValue.rotationNumber,
          autopilot_data.system_id,
          this.parameter.paramType.type,
        )
        autopilot_data.setRebootRequired(true)
      },
    },
  },
  watch: {
    selectedRotation(rotation) {
      this.rotateObject(rotation)
    },
    componentModel() {
      this.add_board_model()
    },
    vehicle_model() {
      this.add_vehicle_model()
    },
  },
  mounted() {
    this.initializeThreeJS()
    window.addEventListener('resize', this.resize)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resize)
    this.cleanupThreeJS()
  },
  methods: {
    cleanupThreeJS() {
      if (this.renderer) {
        this.renderer.dispose()
        this.renderer = undefined
      }
      if (this.scene) {
        this.scene.clear()
        this.scene = undefined
      }
      if (this.camera) {
        this.camera = undefined
      }
      if (this.orbitControls) {
        this.orbitControls.dispose()
        this.orbitControls = undefined
      }
      if (this.object) {
        this.object = undefined
      }
      if (this.vehicle_obj) {
        this.vehicle_obj = undefined
      }
      this.arrows = []
    },
    initializeThreeJS() {
      const scene = new THREE.Scene()
      this.scene = scene
      this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.01, 100)
      this.renderer = new THREE.WebGLRenderer({ antialias: true })
      this.camera.position.set(0.3, 0.3, 0.3)
      if (this.threejs_canvas) {
        while (this.threejs_canvas.firstChild) {
          this.threejs_canvas.removeChild(this.threejs_canvas.firstChild)
        }
        this.threejs_canvas.appendChild(this.renderer.domElement)
      }
      this.orbitControls = new OrbitControls(this.camera, this.renderer.domElement)

      // Add lights
      const ambientLight = new THREE.AmbientLight(0xffffff, 3.5)
      ambientLight.castShadow = true
      scene.add(ambientLight)

      const directionalLight = new THREE.DirectionalLight(0xffffff, 2.0)
      directionalLight.position.set(1, 1, 1)
      directionalLight.castShadow = true
      scene.add(directionalLight)

      const pointLight = new THREE.PointLight(0xffffff, 0.5, 100)
      pointLight.position.set(0, 10, 0)
      pointLight.castShadow = true
      scene.add(pointLight)

      scene.background = new THREE.Color(0xffffff)

      const animate = () : void => {
        requestAnimationFrame(animate)
        if (!this.renderer || !this.camera) {
          return
        }
        this.renderer.render(scene, this.camera)
      }
      this.add_vehicle_model()
      this.add_board_model()
      this.resize()
      this.rotateObject(this.selectedRotation)
      animate()
    },
    rotateObject(rotation: Rotation | undefined) {
      if (!rotation || !this.object) {
        return
      }

      if (rotation.name.startsWith('UNSUPPORTED')) {
        console.warn(`Not visualizing unsupported rotation (${rotation.rotationNumber})`)
        this.object.visible = false
        return
      }

      this.object.visible = true

      // Convert degrees to radians
      const rollRad = THREE.MathUtils.degToRad(rotation.roll)
      const pitchRad = THREE.MathUtils.degToRad(rotation.pitch)
      const yawRad = THREE.MathUtils.degToRad(rotation.yaw)

      // 90° roll transformation to convert between coordinate systems
      const preTransform = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(1, 0, 0),
        Math.PI / 2,
      )

      // -90° roll inverse transformation
      const postTransform = new THREE.Quaternion().setFromAxisAngle(
        new THREE.Vector3(1, 0, 0),
        -Math.PI / 2,
      )

      // Create rotation using aerospace 321 order (ZYX in Three.js)
      const rotationQuaternion = new THREE.Quaternion()
      const euler = new THREE.Euler(rollRad, pitchRad, yawRad, 'ZYX')
      rotationQuaternion.setFromEuler(euler)

      // Apply transformations in sequence
      const finalQuaternion = new THREE.Quaternion()
      finalQuaternion.copy(preTransform)
      finalQuaternion.multiply(rotationQuaternion)
      finalQuaternion.multiply(postTransform)

      this.object.quaternion.copy(finalQuaternion)
    },
    add_vehicle_model() {
      if (this.scene && this.vehicle_model) {
        // Remove existing vehicle model if it exists
        if (this.vehicle_obj) {
          this.scene.remove(this.vehicle_obj)
          this.vehicle_obj = undefined
        }

        const dracoLoader = new DRACOLoader()
        // Get the base path from the imported DRACO files
        const dracoWasmFile = Object.keys(dracoFiles).find((key) => key.includes('draco_decoder.wasm'))
        if (dracoWasmFile) {
          const basePath = dracoFiles[dracoWasmFile].replace(/[^/]*$/, '')
          dracoLoader.setDecoderPath(basePath)
        }
        const loader = new GLTFLoader()
        loader.setDRACOLoader(dracoLoader)
        loader.load(
          this.vehicle_model,
          (gltf: GLTF) => {
            gltf.scene.traverse((child: THREE.Object3D) => {
              if (child instanceof THREE.Mesh) {
                child.material = new THREE.MeshStandardMaterial({
                  color: 0x666666,
                  transparent: true,
                  opacity: 0.05,
                  depthTest: false,
                  depthWrite: true,
                  side: THREE.DoubleSide,
                })
              }
            })
            this.vehicle_obj = gltf.scene
            // Rotate vehicle 90 degrees clockwise around Y axis
            this.vehicle_obj.rotation.y = THREE.MathUtils.degToRad(90)
            if (this.scene) {
              this.scene.add(gltf.scene)
            }
          },
          (progressEvent: ProgressEvent) => {
            console.debug('Loading progress:', progressEvent)
          },
          (error: ErrorEvent) => {
            console.error('An error occurred while loading the GLB model:', error)
          },
        )
      }
    },
    async add_board_model() {
      if (this.scene) {
        try {
          const dracoLoader = new DRACOLoader()
          // Get the base path from the imported DRACO files
          const dracoWasmFile = Object.keys(dracoFiles).find((key) => key.includes('draco_decoder.wasm'))
          if (dracoWasmFile) {
            const basePath = dracoFiles[dracoWasmFile].replace(/[^/]*$/, '')
            dracoLoader.setDecoderPath(basePath)
          }
          const loader = new GLTFLoader()
          loader.setDRACOLoader(dracoLoader)

          const board_model = await get_board_model(this.componentModel)

          let modelPath = ''
          if (typeof board_model === 'string') {
            modelPath = board_model
          } else if (board_model && typeof board_model === 'object' && 'default' in board_model) {
            const modelWithDefault = board_model as { default: string }
            modelPath = modelWithDefault.default
          }

          if (!modelPath) {
            console.error('Invalid board model path returned:', board_model)
            return
          }

          loader.load(
            modelPath,
            (gltf: GLTF) => {
              if (!this.scene) {
                return
              }
              if (this.object) {
                this.scene.remove(this.object)
              }
              this.object = gltf.scene
              this.scene.add(gltf.scene)
              this.rotateObject(this.selectedRotation)
            },
            (progressEvent: ProgressEvent) => {
              console.debug('Loading progress:', progressEvent.loaded, progressEvent.total)
            },
            (error: ErrorEvent) => {
              console.error('An error occurred while loading the GLB model:', error)
            },
          )
        } catch (error) {
          console.error('Error in add_board_model:', error)
        }
      }
    },
    resize() {
      if (!this.camera || !this.renderer || !this.threejs_canvas) {
        return
      }
      this.camera.aspect = this.threejs_canvas.clientWidth / this.threejs_canvas.clientHeight
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(this.threejs_canvas.clientWidth, this.threejs_canvas.clientHeight)
    },
    getUnsupportedRotation(): Rotation {
      if (!this.parameter || this.parameter.value === undefined) {
        return this.unsupportedRotation
      }

      const paramValue = Number(this.parameter.value)
      let valueDisplay = ''

      if (this.parameter) {
        valueDisplay = printParam(this.parameter)
        if (!valueDisplay || valueDisplay === paramValue.toString()) {
          valueDisplay = `Rotation ${paramValue}`
        }
      } else {
        valueDisplay = `Rotation ${paramValue}`
      }

      const rotationName = `UNSUPPORTED - ${valueDisplay}`
      return new Rotation(rotationName, 0, 0, 0, paramValue)
    },
    handleRotationHover(rotation: Rotation) {
      this.hoveredRotation = rotation
      this.rotateObject(rotation)
    },
    handleRotationLeave() {
      this.hoveredRotation = undefined
      this.rotateObject(this.selectedRotation)
    },
  },
}
</script>

<style scoped>
.threejs-relative-container {
  position: relative;
  width: 100%;
  height: 500px;
}

.threejsmount {
  width: 100%;
  height: 100%;
}

.threejs-container {
  width: 100%;
  height: 100%;
}

.orientation-selector-overlay {
  position: absolute;
  top: 16px;
  left: 16px;
  z-index: 2;
  padding: 8px 12px 4px 12px;
  min-width: 220px;
  max-width: 320px;
}
</style>
