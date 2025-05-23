<template>
  <div>
    <v-card outline class="pa-5 mt-4 mr-2 mb-2">
      <v-card-title>Board Orientation</v-card-title>
      <div class="d-flex align-center">
        <v-btn @click="openModal">
          <span class="mr-4">{{ selectedRotation?.name || 'Not Set' }}</span>
          <v-icon>mdi-pencil</v-icon>
        </v-btn>
      </div>
    </v-card>

    <v-dialog v-model="showModal" max-width="98vw" max-height="98vh" class="large-orientation-modal">
      <v-card style="height:90vh;">
        <v-card-title class="headline">
          Board Orientation
          <v-spacer />
          <v-btn icon @click="showModal = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text style="height:calc(80vh - 64px); padding:0;">
          <div class="threejs-relative-container">
            <v-card class="orientation-selector-overlay">
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
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script lang="ts">
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader'
import { PropType } from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import autopilot_data from '@/store/autopilot'
import Parameter, { printParam } from '@/types/autopilot/parameter'

import { get_board_model, get_model } from './viewers/modelHelper'

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
      required: true,
    },
    componentModel: {
      type: String,
      required: false,
      default: undefined,
    },
  },
  data() {
    return {
      showModal: false,
      hoveredRotation: undefined as Rotation | undefined,
      rotations: [
        new Rotation('NONE', 0, 0, 0, 0),
        new Rotation('YAW_45', 0, 0, 45, 1),
        new Rotation('YAW_90', 0, 0, 90, 2),
        new Rotation('YAW_135', 0, 0, 135, 3),
        new Rotation('YAW_180', 0, 0, 180, 4),
        new Rotation('YAW_225', 0, 0, 225, 5),
        new Rotation('YAW_270', 0, 0, 270, 6),
        new Rotation('YAW_315', 0, 0, 315, 7),
        new Rotation('ROLL_180', 180, 0, 0, 8),
        new Rotation('ROLL_180_YAW_45', 180, 0, 45, 9),
        new Rotation('ROLL_180_YAW_90', 180, 0, 90, 10),
        new Rotation('ROLL_180_YAW_135', 180, 0, 135, 11),
        new Rotation('PITCH_180', 0, 180, 0, 12),
        new Rotation('ROLL_180_YAW_225', 180, 0, 225, 13),
        new Rotation('ROLL_180_YAW_270', 180, 0, 270, 14),
        new Rotation('ROLL_180_YAW_315', 180, 0, 315, 15),
        new Rotation('ROLL_90', 90, 0, 0, 16),
        new Rotation('ROLL_90_YAW_45', 90, 0, 45, 17),
        new Rotation('ROLL_90_YAW_90', 90, 0, 90, 18),
        new Rotation('ROLL_90_YAW_135', 90, 0, 135, 19),
        new Rotation('ROLL_270', 270, 0, 0, 20),
        new Rotation('ROLL_270_YAW_45', 270, 0, 45, 21),
        new Rotation('ROLL_270_YAW_90', 270, 0, 90, 22),
        new Rotation('ROLL_270_YAW_135', 270, 0, 135, 23),
        new Rotation('PITCH_90', 0, 90, 0, 24),
        new Rotation('PITCH_270', 0, 270, 0, 25),
        new Rotation('PITCH_180_YAW_90', 0, 180, 90, 26),
        new Rotation('PITCH_180_YAW_270', 0, 180, 270, 27),
        new Rotation('ROLL_90_PITCH_90', 90, 90, 0, 28),
        new Rotation('ROLL_180_PITCH_90', 180, 90, 0, 29),
        new Rotation('ROLL_270_PITCH_90', 270, 90, 0, 30),
        new Rotation('ROLL_90_PITCH_180', 90, 180, 0, 31),
        new Rotation('ROLL_270_PITCH_180', 270, 180, 0, 32),
        new Rotation('ROLL_90_PITCH_270', 90, 270, 0, 33),
        new Rotation('ROLL_180_PITCH_270', 180, 270, 0, 34),
        new Rotation('ROLL_270_PITCH_270', 270, 270, 0, 35),
        new Rotation('ROLL_90_PITCH_180_YAW_90', 90, 180, 90, 36),
        new Rotation('ROLL_90_YAW_270', 90, 0, 270, 37),
        new Rotation('ROLL_90_PITCH_68_YAW_293', 90, 68, 270, 38),
        new Rotation('PITCH_315', 0, 315, 0, 39),
        new Rotation('ROLL_90_PITCH_315', 90, 315, 0, 40),
        new Rotation('PITCH_7', 0, 7, 0, 41),
      ] as Rotation[],
      unsupportedRotation: new Rotation('UNSUPPORTED', 0, 0, 0, -1),
      object: undefined as THREE.WebGLObject,
      camera: undefined as THREE.WebGLCAMERA | undefined,
      scene: undefined as THREE.WebGLScene | undefined,
      renderer: undefined as THREE.WebGLRenderer | undefined,
      vehicle_obj: undefined as THREE.WebGLObject,
      arrows: [] as THREE.WebGLArrowHelper[],
      orbitControls: undefined as OrbitControls | undefined,
    }
  },
  computed: {
    threejs_canvas(): HTMLDivElement {
      return this.$refs.threemount as HTMLDivElement
    },
    vehicle_model(): string | undefined {
      return get_model()
    },
    rotationsWithCustom(): Rotation[] {
      if (this.isUnsupportedRotation) {
        return [this.getUnsupportedRotation(), ...this.rotations]
      }
      return this.rotations
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
    showModal(newValue) {
      if (newValue) {
        // Initialize Three.js when modal opens
        this.$nextTick(() => {
          this.initializeThreeJS()
        })
      } else {
        // Cleanup when modal closes
        this.cleanupThreeJS()
      }
    },
    selectedRotation(rotation) {
      this.rotateObject(rotation)
    },
    componentModel() {
      this.add_board_model()
    },
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
      this.camera.position.y = 0.3
      this.camera.position.x = 0.3
      this.camera.position.z = 0.3
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
        if (!this.renderer) {
          return
        }
        this.renderer.render(scene, this.camera)
      }
      window.addEventListener('resize', this.resize)
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
      if (this.scene) {
        const dracoLoader = new DRACOLoader()
        dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
        const loader = new GLTFLoader()
        loader.setDRACOLoader(dracoLoader)
        loader.load(
          this.vehicle_model,
          (gltf) => {
            gltf.scene.traverse((child) => {
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
            this.scene.add(gltf.scene)
          },
          undefined,
          (progressEvent) => {
            console.log('Loading progress:', progressEvent)
          },
          (error) => {
            console.error('An error occurred while loading the GLB model:', error)
          },
        )
      }
    },
    async add_board_model() {
      if (this.scene) {
        try {
          const dracoLoader = new DRACOLoader()
          dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
          const loader = new GLTFLoader()
          loader.setDRACOLoader(dracoLoader)

          const board_model = await get_board_model(this.componentModel)

          let modelPath = ''
          if (typeof board_model === 'string') {
            modelPath = board_model
          } else if (board_model && board_model.default) {
            modelPath = board_model.default
          }

          if (!modelPath) {
            console.error('Invalid board model path returned:', board_model)
            return
          }

          loader.load(
            modelPath,
            (gltf) => {
              if (this.object) {
                this.scene.remove(this.object)
              }
              this.object = gltf.scene
              this.scene.add(gltf.scene)
              this.rotateObject(this.selectedRotation)
            },
            (error) => {
              console.error('An error occurred while loading the GLB model:', error)
            },
          )
        } catch (error) {
          console.error('Error in add_board_model:', error)
        }
      }
    },
    resize() {
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
    openModal() {
      this.showModal = true
      this.$nextTick(() => {
        setTimeout(() => {
          this.resize()
        }, 300) // Adjust delay as needed for modal animation
      })
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
.large-orientation-modal .v-card {
  width: 80vw;
  max-width: 88vw;
  height: 80vh;
  max-height: 88vh;
}

.large-orientation-modal .v-card-text {
  height: calc(80vh - 64px);
  overflow: auto;
}

div.threejsmount {
  width: 100%;
  height: calc(80vh - 64px);
  margin-top: 16px;
}

.threejs-relative-container {
  position: relative;
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

.threejs-container, .threejsmount {
  width: 100%;
  height: 100%;
}

.v-dialog {
  overflow: hidden;
}
</style>
