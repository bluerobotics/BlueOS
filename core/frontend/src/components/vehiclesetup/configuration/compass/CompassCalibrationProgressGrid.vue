<template>
  <div
    ref="threeMount"
    class="geodesic-grid-three"
  />
</template>

<script lang="ts">
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls'
import Vue, { PropType } from 'vue'

type Point3D = [number, number, number]
type Triangle3D = [Point3D, Point3D, Point3D]

const AP_GOLDEN_RATIO = (1 + Math.sqrt(5)) / 2
const AP_GRID_RADIUS = Math.sqrt(1 + AP_GOLDEN_RATIO ** 2)
const AP_MIDPOINT_SCALE = AP_GRID_RADIUS / (2 * AP_GOLDEN_RATIO)

const AP_ICO_TRIANGLES_FIRST_HALF: Triangle3D[] = [
  [[-AP_GOLDEN_RATIO, 1, 0], [-1, 0, -AP_GOLDEN_RATIO], [-AP_GOLDEN_RATIO, -1, 0]],
  [[-1, 0, -AP_GOLDEN_RATIO], [-AP_GOLDEN_RATIO, -1, 0], [0, -AP_GOLDEN_RATIO, -1]],
  [[-AP_GOLDEN_RATIO, -1, 0], [0, -AP_GOLDEN_RATIO, -1], [0, -AP_GOLDEN_RATIO, 1]],
  [[-1, 0, -AP_GOLDEN_RATIO], [0, -AP_GOLDEN_RATIO, -1], [1, 0, -AP_GOLDEN_RATIO]],
  [[0, -AP_GOLDEN_RATIO, -1], [0, -AP_GOLDEN_RATIO, 1], [AP_GOLDEN_RATIO, -1, 0]],
  [[0, -AP_GOLDEN_RATIO, -1], [1, 0, -AP_GOLDEN_RATIO], [AP_GOLDEN_RATIO, -1, 0]],
  [[AP_GOLDEN_RATIO, -1, 0], [1, 0, -AP_GOLDEN_RATIO], [AP_GOLDEN_RATIO, 1, 0]],
  [[1, 0, -AP_GOLDEN_RATIO], [AP_GOLDEN_RATIO, 1, 0], [0, AP_GOLDEN_RATIO, -1]],
  [[1, 0, -AP_GOLDEN_RATIO], [0, AP_GOLDEN_RATIO, -1], [-1, 0, -AP_GOLDEN_RATIO]],
  [[0, AP_GOLDEN_RATIO, -1], [-AP_GOLDEN_RATIO, 1, 0], [-1, 0, -AP_GOLDEN_RATIO]],
]

const AP_ICO_TRIANGLES_SECOND_HALF: Triangle3D[] = AP_ICO_TRIANGLES_FIRST_HALF
  .map(([a, b, c]) => [[-a[0], -a[1], -a[2]], [-b[0], -b[1], -b[2]], [-c[0], -c[1], -c[2]]])

const AP_ICO_TRIANGLES = AP_ICO_TRIANGLES_FIRST_HALF.concat(AP_ICO_TRIANGLES_SECOND_HALF)

function midpointProjection(a: Point3D, b: Point3D): Point3D {
  return [
    AP_MIDPOINT_SCALE * (a[0] + b[0]),
    AP_MIDPOINT_SCALE * (a[1] + b[1]),
    AP_MIDPOINT_SCALE * (a[2] + b[2]),
  ]
}

function buildGeodesicSections(): Triangle3D[] {
  const sections: Triangle3D[] = []
  for (const [a, b, c] of AP_ICO_TRIANGLES) {
    const ma = midpointProjection(a, b)
    const mb = midpointProjection(b, c)
    const mc = midpointProjection(c, a)
    sections.push([ma, mb, mc], [a, ma, mc], [ma, b, mb], [mc, mb, c])
  }
  return sections
}

function determinant([a0, a1, a2]: Point3D, [b0, b1, b2]: Point3D, [c0, c1, c2]: Point3D): number {
  return a0 * (b1 * c2 - b2 * c1) - b0 * (a1 * c2 - a2 * c1) + c0 * (a1 * b2 - a2 * b1)
}

const AP_GEODESIC_SECTIONS = buildGeodesicSections()

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
  },
  data() {
    return {
      current_section: -1,
      last_section: -1,
      scene: undefined as THREE.Scene | undefined,
      camera: undefined as THREE.PerspectiveCamera | undefined,
      renderer: undefined as THREE.WebGLRenderer | undefined,
      orbitControls: undefined as OrbitControls | undefined,
      sectionMeshes: [] as THREE.Mesh[],
      directionArrow: undefined as THREE.ArrowHelper | undefined,
      directionMarker: undefined as THREE.Mesh | undefined,
      animationFrameId: undefined as number | undefined,
      previous_completion_mask: [] as number[],
      cameraTweenStart: undefined as THREE.Vector3 | undefined,
      cameraTweenEnd: undefined as THREE.Vector3 | undefined,
      cameraTweenStartMs: 0,
      cameraTweenDurationMs: 700,
    }
  },
  computed: {
    three_mount(): HTMLDivElement {
      return this.$refs.threeMount as HTMLDivElement
    },
    direction_key(): string {
      return `${this.directionX}:${this.directionY}:${this.directionZ}`
    },
  },
  watch: {
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
        this.rotateToNewlyCheckedSection()
        this.updateSectionStyles()
        this.previous_completion_mask = [...this.completionMask]
      },
    },
  },
  mounted() {
    this.initializeScene()
    window.addEventListener('resize', this.handleResize)
    this.handleResize()
    this.updateCurrentAndLastSections()
    this.updateDirectionIndicator()
    this.updateSectionStyles()
    this.previous_completion_mask = [...this.completionMask]
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
      this.camera.position.set(0, 0, 6)

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

      this.createGeodesicMeshes()
    },
    createGeodesicMeshes() {
      if (!this.scene) {
        return
      }

      this.sectionMeshes = []
      for (const [section, [a, b, c]] of AP_GEODESIC_SECTIONS.entries()) {
        const geometry = new THREE.BufferGeometry()
        geometry.setAttribute('position', new THREE.Float32BufferAttribute([...a, ...b, ...c], 3))
        geometry.computeVertexNormals()

        const material = new THREE.MeshStandardMaterial({
          color: COLOR_PENDING,
          side: THREE.DoubleSide,
          transparent: true,
          opacity: 0.52,
          roughness: 0.82,
          metalness: 0.04,
          emissive: 0x000000,
        })

        const mesh = new THREE.Mesh(geometry, material)
        mesh.userData.section = section
        this.scene.add(mesh)
        this.sectionMeshes.push(mesh)
      }
    },
    sectionCompleted(section: number): boolean {
      const byte = this.completionMask[Math.floor(section / 8)] ?? 0
      return (byte & 1 << section % 8) !== 0
    },
    sectionCompletedInMask(mask: number[], section: number): boolean {
      const byte = mask[Math.floor(section / 8)] ?? 0
      return (byte & 1 << section % 8) !== 0
    },
    findSectionByDirection(direction_x: number, direction_y: number, direction_z: number): number {
      const eps = 1e-6
      for (let section = 0; section < AP_GEODESIC_SECTIONS.length; section += 1) {
        const [a, b, c] = AP_GEODESIC_SECTIONS[section]
        const det = determinant(a, b, c)
        if (Math.abs(det) < eps) {
          continue
        }
        const x = determinant([direction_x, direction_y, direction_z], b, c) / det
        const y = determinant(a, [direction_x, direction_y, direction_z], c) / det
        const z = determinant(a, b, [direction_x, direction_y, direction_z]) / det
        if (x >= -eps && y >= -eps && z >= -eps) {
          return section
        }
      }
      return -1
    },
    updateCurrentAndLastSections() {
      const nextSection = this.findSectionByDirection(this.directionX, this.directionY, this.directionZ)
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
      const direction = new THREE.Vector3(this.directionX, this.directionY, this.directionZ)
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
    rotateToNewlyCheckedSection() {
      if (this.previous_completion_mask.length === 0) {
        return
      }
      const newCompletedSections: number[] = []
      for (let section = 0; section < AP_GEODESIC_SECTIONS.length; section += 1) {
        const wasCompleted = this.sectionCompletedInMask(this.previous_completion_mask, section)
        const isCompleted = this.sectionCompletedInMask(this.completionMask, section)
        if (!wasCompleted && isCompleted) {
          newCompletedSections.push(section)
        }
      }

      if (newCompletedSections.length === 0) {
        return
      }
      const latestSection = newCompletedSections[newCompletedSections.length - 1]
      this.rotateCameraToSection(latestSection)
    },
    rotateCameraToSection(section: number) {
      if (!this.camera || !this.orbitControls) {
        return
      }
      const [a, b, c] = AP_GEODESIC_SECTIONS[section]
      const sectionCenter = new THREE.Vector3(
        (a[0] + b[0] + c[0]) / 3,
        (a[1] + b[1] + c[1]) / 3,
        (a[2] + b[2] + c[2]) / 3,
      ).normalize()

      const distanceFromTarget = this.camera.position.distanceTo(this.orbitControls.target)
      this.cameraTweenStart = this.camera.position.clone()
      this.cameraTweenEnd = sectionCenter.multiplyScalar(Math.max(distanceFromTarget, 4.2))
      this.cameraTweenStartMs = performance.now()
    },
    updateCameraTween() {
      if (!this.camera || !this.orbitControls || !this.cameraTweenStart || !this.cameraTweenEnd) {
        return
      }
      const elapsed = performance.now() - this.cameraTweenStartMs
      const t = Math.min(Math.max(elapsed / this.cameraTweenDurationMs, 0), 1)
      const eased = 1 - (1 - t) ** 3
      this.camera.position.lerpVectors(this.cameraTweenStart, this.cameraTweenEnd, eased)
      this.orbitControls.target.set(0, 0, 0)
      if (t >= 1) {
        this.cameraTweenStart = undefined
        this.cameraTweenEnd = undefined
      }
    },
    updateSectionStyles() {
      for (const [section, mesh] of this.sectionMeshes.entries()) {
        const material = mesh.material as THREE.MeshStandardMaterial
        const completed = this.sectionCompleted(section)

        material.color.setHex(completed ? COLOR_COMPLETE : COLOR_PENDING)
        material.opacity = completed ? 0.95 : 0.22
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
          material.opacity = 1
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
      this.updateCameraTween()
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
