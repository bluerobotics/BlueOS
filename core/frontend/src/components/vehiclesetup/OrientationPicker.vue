<template>
  <v-card outline class="pa-5 mt-4 mr-2 mb-2">
    <v-select
      v-model="selectedRotation"
      class="orientation-selector"
      :items="rotations"
      return-object
      :item-text="'name'"
    />
    <div ref="threemount" class="threejsmount" />
  </v-card>
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

  constructor(name: string, roll: number, pitch: number, yaw: number) {
    this.name = name
    this.roll = roll
    this.pitch = pitch
    this.yaw = yaw
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
      rotations: [
        new Rotation('NONE', 0, 0, 0),
        new Rotation('YAW_45', 0, 0, 45),
        new Rotation('YAW_90', 0, 0, 90),
        new Rotation('YAW_135', 0, 0, 135),
        new Rotation('YAW_180', 0, 0, 180),
        new Rotation('YAW_225', 0, 0, 225),
        new Rotation('YAW_270', 0, 0, 270),
        new Rotation('YAW_315', 0, 0, 315),
        new Rotation('ROLL_180', 180, 0, 0),
        new Rotation('ROLL_180_YAW_45', 180, 0, 45),
        new Rotation('ROLL_180_YAW_90', 180, 0, 90),
        new Rotation('ROLL_180_YAW_135', 180, 0, 135),
        new Rotation('PITCH_180', 0, 180, 0),
        new Rotation('ROLL_180_YAW_225', 180, 0, 225),
        new Rotation('ROLL_180_YAW_270', 180, 0, 270),
        new Rotation('ROLL_180_YAW_315', 180, 0, 315),
        new Rotation('ROLL_90', 90, 0, 0),
        new Rotation('ROLL_90_YAW_45', 90, 0, 45),
        new Rotation('ROLL_90_YAW_90', 90, 0, 90),
        new Rotation('ROLL_90_YAW_135', 90, 0, 135),
        new Rotation('ROLL_270', 270, 0, 0),
        new Rotation('ROLL_270_YAW_45', 270, 0, 45),
        new Rotation('ROLL_270_YAW_90', 270, 0, 90),
        new Rotation('ROLL_270_YAW_135', 270, 0, 135),
        new Rotation('PITCH_90', 0, 90, 0),
        new Rotation('PITCH_270', 0, 270, 0),
        new Rotation('PITCH_180_YAW_90', 0, 180, 90),
        new Rotation('PITCH_180_YAW_270', 0, 180, 270),
        new Rotation('ROLL_90_PITCH_90', 90, 90, 0),
        new Rotation('ROLL_180_PITCH_90', 180, 90, 0),
        new Rotation('ROLL_270_PITCH_90', 270, 90, 0),
        new Rotation('ROLL_90_PITCH_180', 90, 180, 0),
        new Rotation('ROLL_270_PITCH_180', 270, 180, 0),
        new Rotation('ROLL_90_PITCH_270', 90, 270, 0),
        new Rotation('ROLL_180_PITCH_270', 180, 270, 0),
        new Rotation('ROLL_270_PITCH_270', 270, 270, 0),
        new Rotation('ROLL_90_PITCH_180_YAW_90', 90, 180, 90),
        new Rotation('ROLL_90_YAW_270', 90, 0, 270),
        new Rotation('ROLL_90_PITCH_68_YAW_293', 90, 68, 270),
        new Rotation('PITCH_315', 0, 315, 0),
        new Rotation('ROLL_90_PITCH_315', 90, 315, 0),
        new Rotation('PITCH_7', 0, 7, 0),
      ] as Rotation[],
      object: undefined as THREE.WebGLObject,
      camera: undefined as THREE.WebGLCAMERA | undefined,
      scene: undefined as THREE.WebGLScene | undefined,
      renderer: undefined as THREE.WebGLRenderer | undefined,
      vehicle_obj: undefined as THREE.WebGLObject,
      arrows: [] as THREE.WebGLArrowHelper[],
    }
  },
  computed: {
    threejs_canvas(): HTMLDivElement {
      return this.$refs.threemount as HTMLDivElement
    },
    vehicle_model(): string | undefined {
      return get_model()
    },
    selectedRotation: {
      get(): Rotation | undefined {
        return this.rotations.find(
          (rotation) => {
            const rotation_lowercase = rotation.name.toLocaleLowerCase().replace('_', '')
            const param_lowercase = printParam(this.parameter).toLocaleLowerCase()
            return rotation_lowercase === param_lowercase
          },
        )
      },
      set(newValue: Rotation) {
        if (this.parameter === undefined) {
          return
        }
        mavlink2rest.setParam(
          this.parameter.name,
          this.rotations.indexOf(newValue),
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
  },
  mounted() {
    const scene = new THREE.Scene()
    this.scene = scene
    this.camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.01, 100)
    this.renderer = new THREE.WebGLRenderer({ antialias: true })
    this.camera.position.y = 0.3
    this.camera.position.x = 0.3
    this.camera.position.z = 0.3
    if (this.threejs_canvas) {
      this.threejs_canvas.appendChild(this.renderer.domElement)
    }
    const controls = new OrbitControls(this.camera, this.renderer.domElement)

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

    // Add arrows for the x, y, and z axes
    const arrowHelperX = new THREE.ArrowHelper(new THREE.Vector3(0.1, 0, 0), new THREE.Vector3(0, 0, 0), 0.1, 0xff0000)
    this.arrows.push(arrowHelperX)
    scene.add(arrowHelperX)

    const arrowHelperY = new THREE.ArrowHelper(new THREE.Vector3(0, 5, 0), new THREE.Vector3(0, 0, 0), 0.1, 0x00ff00)
    scene.add(arrowHelperY)
    this.arrows.push(arrowHelperY)

    const arrowHelperZ = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 5), new THREE.Vector3(0, 0, 0), 0.1, 0x0000ff)
    scene.add(arrowHelperZ)
    this.arrows.push(arrowHelperZ)

    const animate = () : void => {
      requestAnimationFrame(animate)
      controls.update()
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
  beforeDestroy() {
    window.removeEventListener('resize', this.resize)
  },
  methods: {
    rotateObject(rotation: Rotation | undefined) {
      if (!rotation) {
        return
      }
      if (this.object) {
        this.object.rotation.x = THREE.MathUtils.degToRad(rotation.roll)
        this.object.rotation.z = THREE.MathUtils.degToRad(rotation.pitch)
        this.object.rotation.y = THREE.MathUtils.degToRad(rotation.yaw)
      }
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
                  color: 0x666666, // white
                  transparent: true,
                  opacity: 0.05,
                  depthTest: false,
                  depthWrite: true,
                  side: THREE.DoubleSide, // Set material to be double-sided
                })
              }
            })
            this.vehicle_obj = gltf.scene
            this.scene.add(gltf.scene)
          },
          undefined,
          (error) => {
            console.error('An error occurred while loading the GLB model:', error)
          },
        )
      }
    },
    async add_board_model() {
      if (this.scene) {
        const dracoLoader = new DRACOLoader()
        dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
        const loader = new GLTFLoader()
        loader.setDRACOLoader(dracoLoader)
        const board_model = await get_board_model(this.componentModel)
        console.log(board_model.default)
        loader.load(
          board_model.default,
          (gltf) => {
            this.object = gltf.scene
            this.scene.add(gltf.scene)
            this.rotateObject(this.selectedRotation)
          },
          undefined,
          (error) => {
            console.error('An error occurred while loading the GLB model:', error)
          },
        )
      }
    },
    resize() {
      if (!this.threejs_canvas?.clientWidth || !this.threejs_canvas?.clientHeight) {
        return
      }
      this.camera.aspect = this.threejs_canvas.clientWidth / this.threejs_canvas.clientHeight
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(this.threejs_canvas.clientWidth, this.threejs_canvas.clientHeight)
    },
  },
}
</script>

<style scoped>

div.threejsmount {
  width: 100%;
  height: 300px;
}

.orientation-selector {
  width: 350px;
}

</style>
