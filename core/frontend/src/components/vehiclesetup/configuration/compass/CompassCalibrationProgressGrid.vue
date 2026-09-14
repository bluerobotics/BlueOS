<template>
  <div
    ref="threeMount"
    class="geodesic-grid-three"
  />
</template>

<script lang="ts">
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import { GLTF } from 'three/examples/jsm/loaders/GLTFLoader'
import Vue, { PropType } from 'vue'

import autopilot_data from '@/store/autopilot'
import { makeGLTFLoader } from '@/utils/draco'

import {
  AP_GEODESIC_SECTIONS, AP_GRID_RADIUS, modelRotationFromAttitude, sectionByDirection, sectionCompleted,
  toModelFrame,
} from './geodesic_grid'

// Fraction of the grid radius spanned by the longest axis of the vehicle, it only has to read as a
// reference for which way the sections sit relative to the vehicle
const MODEL_SPAN_IN_RADII = 1.15

const COLOR_PENDING = 0x9ea4ac
const COLOR_COMPLETE = 0x29b6ff
const COLOR_CURRENT = 0xffeb3b
const COLOR_LAST = 0xf57c00

export default Vue.extend({
  name: 'CompassCalibrationProgressGrid',
  props: {
    completionMask: {
      type: Array as PropType<number[]>,
      required: true,
    },
    directionX: {
      type: Number,
      required: true,
    },
    directionY: {
      type: Number,
      required: true,
    },
    directionZ: {
      type: Number,
      required: true,
    },
    roll: {
      type: Number,
      required: true,
    },
    pitch: {
      type: Number,
      required: true,
    },
    yaw: {
      type: Number,
      required: true,
    },
  },
  data() {
    return {
      current_section: -1,
      last_section: -1,
      scene: undefined as THREE.Scene | undefined,
      camera: undefined as THREE.PerspectiveCamera | undefined,
      renderer: undefined as THREE.WebGLRenderer | undefined,
      orbitControls: undefined as OrbitControls | undefined,
      // the vehicle and its body fixed grid turn together, the field does not
      bodyGroup: undefined as THREE.Group | undefined,
      sectionMeshes: [] as THREE.Mesh[],
      vehicleObject: undefined as THREE.Object3D | undefined,
      directionArrow: undefined as THREE.ArrowHelper | undefined,
      directionMarker: undefined as THREE.Mesh | undefined,
      animationFrameId: undefined as number | undefined,
    }
  },
  computed: {
    three_mount(): HTMLDivElement {
      return this.$refs.threeMount as HTMLDivElement
    },
    vehicle_model(): string {
      return autopilot_data.vehicle_model
    },
    direction_key(): string {
      return `${this.directionX}:${this.directionY}:${this.directionZ}`
    },
    attitude_rotation(): THREE.Quaternion {
      return modelRotationFromAttitude(this.roll, this.pitch, this.yaw)
    },
  },
  watch: {
    vehicle_model: {
      handler() {
        this.addVehicleModel()
      },
    },
    attitude_rotation: {
      immediate: true,
      handler() {
        this.updateAttitude()
        this.updateDirectionIndicator()
      },
    },
    direction_key: {
      immediate: true,
      handler() {
        this.updateCurrentAndLastSections()
        this.updateDirectionIndicator()
        this.updateSectionStyles()
      },
    },
    completionMask: {
      deep: true,
      handler() {
        this.updateSectionStyles()
      },
    },
  },
  mounted() {
    this.initializeScene()
    window.addEventListener('resize', this.handleResize)
    this.handleResize()
    this.updateAttitude()
    this.updateCurrentAndLastSections()
    this.updateDirectionIndicator()
    this.updateSectionStyles()
    this.animate()
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.handleResize)
    if (this.animationFrameId !== undefined) {
      window.cancelAnimationFrame(this.animationFrameId)
    }
    this.orbitControls?.dispose()
    this.renderer?.dispose()
  },
  methods: {
    initializeScene() {
      this.scene = new THREE.Scene()

      this.camera = new THREE.PerspectiveCamera(45, 1, 0.01, 100)
      // looking at the vehicle from above its starboard bow, so forward and up read correctly
      this.camera.position.set(3.8, 2.5, 3.8)

      this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      this.renderer.setPixelRatio(window.devicePixelRatio)

      if (this.three_mount) {
        while (this.three_mount.firstChild) {
          this.three_mount.removeChild(this.three_mount.firstChild)
        }
        this.three_mount.appendChild(this.renderer.domElement)
      }

      this.orbitControls = new OrbitControls(this.camera, this.renderer.domElement)
      this.orbitControls.enableDamping = true
      this.orbitControls.enablePan = false
      this.orbitControls.minDistance = 2.2
      this.orbitControls.maxDistance = 10

      const ambientLight = new THREE.AmbientLight(0xffffff, 0.9)
      this.scene.add(ambientLight)
      const directionalLight = new THREE.DirectionalLight(0xffffff, 0.75)
      directionalLight.position.set(1.5, 1.2, 2.5)
      this.scene.add(directionalLight)

      this.bodyGroup = new THREE.Group()
      this.scene.add(this.bodyGroup)

      this.createGeodesicMeshes()
      this.addVehicleModel()
    },
    updateAttitude() {
      this.bodyGroup?.quaternion.copy(this.attitude_rotation)
    },
    addVehicleModel() {
      if (!this.bodyGroup || !this.vehicle_model) {
        return
      }
      makeGLTFLoader().load(
        this.vehicle_model,
        (gltf: GLTF) => {
          if (!this.bodyGroup) {
            return
          }
          if (this.vehicleObject) {
            this.bodyGroup.remove(this.vehicleObject)
          }

          const bounds = new THREE.Box3().setFromObject(gltf.scene)
          const longest = Math.max(...bounds.getSize(new THREE.Vector3()).toArray())
          const scale = longest > 0 ? MODEL_SPAN_IN_RADII * AP_GRID_RADIUS / longest : 1
          gltf.scene.scale.setScalar(scale)
          // the models face +z, so the nose only lands on the body frame's forward axis after a
          // quarter turn about up, the same one OrientationPicker gives them
          gltf.scene.rotation.y = Math.PI / 2
          // the models are not centred on their own origin, and the grid is centred on the vehicle
          gltf.scene.position.copy(
            bounds.getCenter(new THREE.Vector3()).multiplyScalar(-scale).applyEuler(gltf.scene.rotation),
          )

          this.vehicleObject = gltf.scene
          this.bodyGroup.add(gltf.scene)
        },
        undefined,
        (error: ErrorEvent) => console.error('Failed to load the vehicle model for the calibration grid:', error),
      )
    },
    createGeodesicMeshes() {
      if (!this.bodyGroup) {
        return
      }

      this.sectionMeshes = []
      for (const [section, [a, b, c]] of AP_GEODESIC_SECTIONS.entries()) {
        const [pa, pb, pc] = [toModelFrame(a), toModelFrame(b), toModelFrame(c)]
        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.Float32BufferAttribute([...pa, ...pb, ...pc], 3))
        geometry.computeVertexNormals()

        const material = new THREE.MeshStandardMaterial({
          color: COLOR_PENDING,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.52,
          roughness: 0.82,
          metalness: 0.04,
          emissive: 0x000000,
          // the shell surrounds the vehicle, without this its far half hides the model inside
          depthWrite: false,
        })

        const mesh = new THREE.Mesh(geometry, material)
        mesh.userData.section = section
        this.bodyGroup.add(mesh)
        this.sectionMeshes.push(mesh)
      }
    },
    updateCurrentAndLastSections() {
      const nextSection = sectionByDirection([this.directionX, this.directionY, this.directionZ])
      if (nextSection >= 0 && this.current_section >= 0 && nextSection !== this.current_section) {
        this.last_section = this.current_section
      } else if (this.last_section < 0) {
        this.last_section = nextSection
      }
      this.current_section = nextSection
    },
    updateDirectionIndicator() {
      if (!this.scene) {
        return
      }
      // the grid turns with the vehicle, so the field has to be drawn where the vehicle's own
      // attitude puts it, which leaves it pointing the same way in the world as the vehicle turns
      const direction = new THREE.Vector3(...toModelFrame([this.directionX, this.directionY, this.directionZ]))
        .applyQuaternion(this.attitude_rotation)
      if (direction.lengthSq() <= 1e-8) {
        return
      }

      direction.normalize()
      const length = AP_GRID_RADIUS * 1.4
      const origin = new THREE.Vector3(0, 0, 0)

      if (!this.directionArrow) {
        this.directionArrow = new THREE.ArrowHelper(direction, origin, length, 0xffffff, 0.22, 0.11)
        this.scene.add(this.directionArrow)
      } else {
        this.directionArrow.setDirection(direction)
        this.directionArrow.setLength(length, 0.22, 0.11)
      }

      const markerPosition = direction.clone().multiplyScalar(length)
      if (!this.directionMarker) {
        const markerGeometry = new THREE.SphereGeometry(0.085, 18, 18)
        const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xffc107 })
        this.directionMarker = new THREE.Mesh(markerGeometry, markerMaterial)
        this.scene.add(this.directionMarker)
      }
      this.directionMarker.position.copy(markerPosition)
    },
    updateSectionStyles() {
      for (const [section, mesh] of this.sectionMeshes.entries()) {
        const material = mesh.material as THREE.MeshStandardMaterial
        const completed = sectionCompleted(this.completionMask, section)

        material.color.setHex(completed ? COLOR_COMPLETE : COLOR_PENDING)
        material.opacity = completed ? 0.6 : 0.14
        material.emissive.setHex(0x000000)
        material.emissiveIntensity = 0
        mesh.scale.setScalar(1)

        if (section === this.last_section && section !== this.current_section) {
          material.emissive.setHex(COLOR_LAST)
          material.emissiveIntensity = 0.24
          mesh.scale.setScalar(1.01)
        }

        if (section === this.current_section) {
          material.emissive.setHex(COLOR_CURRENT)
          material.emissiveIntensity = 0.45
          material.opacity = 0.85
          mesh.scale.setScalar(1.04)
        }

        material.needsUpdate = true
      }
    },
    handleResize() {
      if (!this.renderer || !this.camera || !this.three_mount) {
        return
      }
      const width = this.three_mount.clientWidth
      const height = this.three_mount.clientHeight
      if (!width || !height) {
        return
      }

      this.camera.aspect = width / height
      this.camera.updateProjectionMatrix()
      this.renderer.setSize(width, height)
    },
    animate() {
      this.animationFrameId = window.requestAnimationFrame(this.animate)
      this.orbitControls?.update()
      if (this.renderer && this.scene && this.camera) {
        this.renderer.render(this.scene, this.camera)
      }
    },
  },
})
</script>

<style scoped>
.geodesic-grid-three {
  width: 100%;
  height: 250px;
  margin: 0 auto;
  display: block;
  cursor: grab;
}

.geodesic-grid-three:active {
  cursor: grabbing;
}
</style>
