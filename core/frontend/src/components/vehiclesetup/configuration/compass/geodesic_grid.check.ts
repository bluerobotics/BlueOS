/**
 * Self-check for geodesic_grid.ts, run it with `bun geodesic_grid.check.ts`.
 *
 * The section numbering has to agree with the autopilot or the completion mask lights up the wrong
 * triangles, so the expectations below are taken from ArduPilot's own test of AP_GeodesicGrid,
 * libraries/AP_Math/tests/test_geodesic_grid.cpp, plus the frame conventions this display relies on.
 */
import * as THREE from 'three'

import {
  AP_GEODESIC_SECTIONS, AP_GRID_RADIUS, modelRotationFromAttitude, Point3D, sectionByDirection,
  sectionCompleted, toModelFrame,
} from './geodesic_grid'

const GOLDEN = (1 + Math.sqrt(5)) / 2

let failures = 0

function check(name: string, passed: boolean, detail = ''): void {
  if (!passed) {
    failures += 1
  }
  console.log(`${passed ? 'ok  ' : 'FAIL'} ${name}${detail ? ` (${detail})` : ''}`)
}

// The icosahedron tessellated by two gives 20 * 4 triangles, and the mask has one bit for each
check('80 sections', AP_GEODESIC_SECTIONS.length === 80, `got ${AP_GEODESIC_SECTIONS.length}`)

// Every vertex sits on the circumscribed sphere, otherwise the sections do not tile it
const worstRadius = Math.max(
  ...AP_GEODESIC_SECTIONS.flat().map(([x, y, z]) => Math.abs(Math.hypot(x, y, z) - AP_GRID_RADIUS)),
)
check('vertices on the grid sphere', worstRadius < 1e-9, `worst off by ${worstRadius.toExponential(2)}`)

/*
 * ArduPilot's HardcodedVectors cases. These are deliberately not centroids, so they pin the
 * numbering rather than just our own definition of where each section is.
 */
const hardcoded: [Point3D, number][] = [
  [[0.25 * GOLDEN, -0.25 * (13 * GOLDEN + 1), -1.25], 17],
  [[-0.2667, 0.1667 * GOLDEN, 2.2667 * GOLDEN + 0.1667], 55],
  [[-0.875, 6.125 * GOLDEN, -1.125 * GOLDEN - 6.125], 34],
]
for (const [direction, expected] of hardcoded) {
  const section = sectionByDirection(direction)
  check(`hardcoded vector maps to section ${expected}`, section === expected, `got ${section}`)
}

// A vector along an edge belongs to both of the sections sharing it, ArduPilot allows either
const onEdge = sectionByDirection([GOLDEN, -4 * GOLDEN - 1, 1])
check('vector on a shared edge picks one of its sections', [16, 18].includes(onEdge), `got ${onEdge}`)

/*
 * ArduPilot's GeneralVectors cases: for every section, the vector through its centroid and vectors
 * crossing it near each edge and each vertex must all resolve to that same section.
 */
let wrongSection = 0
for (const [section, [a, b, c]] of AP_GEODESIC_SECTIONS.entries()) {
  const combine = (wa: number, wb: number, wc: number): Point3D => [
    wa * a[0] + wb * b[0] + wc * c[0],
    wa * a[1] + wb * b[1] + wc * c[1],
    wa * a[2] + wb * b[2] + wc * c[2],
  ]
  const probes: Point3D[] = [
    combine(1, 1, 1),
    combine(1, 1, 0.001), combine(1, 0.001, 1), combine(0.001, 1, 1),
    combine(1, 0.001, 0.001), combine(0.001, 1, 0.001), combine(0.001, 0.001, 1),
  ]
  if (probes.some((probe) => sectionByDirection(probe) !== section)) {
    wrongSection += 1
  }
}
check('centroid, edge and vertex probes resolve to their own section', wrongSection === 0, `${wrongSection}/80 wrong`)

// The null vector crosses nothing, it used to satisfy the test for every section and report 0
check('the null vector has no section', sectionByDirection([0, 0, 0]) === -1)

// 80 bits little endian over 10 bytes, as MAG_CAL_PROGRESS packs them
check('mask bit 0 is the first byte', sectionCompleted([1, 0, 0, 0, 0, 0, 0, 0, 0, 0], 0))
check('mask bit 79 is the last byte', sectionCompleted([0, 0, 0, 0, 0, 0, 0, 0, 0, 0x80], 79))
check('mask bit 8 is not bit 0', !sectionCompleted([1, 0, 0, 0, 0, 0, 0, 0, 0, 0], 8))
check('a short mask reads as incomplete', !sectionCompleted([], 40))

/*
 * The body to model frame mapping has to be a rotation. A reflection would mirror the grid, showing
 * the operator sections on the wrong side of the vehicle.
 */
const [mx, my, mz] = [toModelFrame([1, 0, 0]), toModelFrame([0, 1, 0]), toModelFrame([0, 0, 1])]
const dot = (u: Point3D, v: Point3D) => u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
const determinant = dot(mx, [
  my[1] * mz[2] - my[2] * mz[1], my[2] * mz[0] - my[0] * mz[2], my[0] * mz[1] - my[1] * mz[0],
])
check('body to model frame is a rotation, not a reflection', determinant === 1, `determinant ${determinant}`)
check('orthonormal axes', [dot(mx, my), dot(my, mz), dot(mz, mx)].every((d) => d === 0))

// The models are x forward, y up, z right, which is what the grid has to line up with
check('vehicle forward stays forward', `${toModelFrame([1, 0, 0])}` === `${[1, 0, 0]}`)
check('vehicle right maps to model right', `${toModelFrame([0, 1, 0])}` === `${[0, 0, 1]}`)
check('vehicle down maps to model down', `${toModelFrame([0, 0, 1])}` === `${[0, -1, 0]}`)

/*
 * The attitude rotation turns the vehicle and its grid under a field that stays put, so getting the
 * euler convention wrong would draw the vehicle in an orientation it is not in. Body forward, right
 * and down are checked against where the model frame puts north, east and up.
 */
const DEG = Math.PI / 180
const BODY_FORWARD: Point3D = [1, 0, 0]
const BODY_RIGHT: Point3D = [0, 1, 0]
const BODY_DOWN: Point3D = [0, 0, 1]

function rotated(body: Point3D, roll: number, pitch: number, yaw: number): Point3D {
  const vector = new THREE.Vector3(...toModelFrame(body))
    .applyQuaternion(modelRotationFromAttitude(roll * DEG, pitch * DEG, yaw * DEG))
  return [vector.x, vector.y, vector.z].map((value) => Math.round(value * 1e6) / 1e6) as Point3D
}

const points = (axis: Point3D, expected: Point3D) => `${axis}` === `${expected}`

// Level and heading north, so the model frame's own axes: north along x, east along z, up along y
check('level: forward is north', points(rotated(BODY_FORWARD, 0, 0, 0), [1, 0, 0]))
check('level: right is east', points(rotated(BODY_RIGHT, 0, 0, 0), [0, 0, 1]))
check('level: down is down', points(rotated(BODY_DOWN, 0, 0, 0), [0, -1, 0]))

// Yaw is a turn about the vertical, and a quarter turn to starboard leaves the nose facing east
check('yaw 90: forward is east', points(rotated(BODY_FORWARD, 0, 0, 90), [0, 0, 1]))
check('yaw 90: stays level', points(rotated(BODY_DOWN, 0, 0, 90), [0, -1, 0]))

// Rolling to starboard puts the right hand side down and the top to starboard
check('roll 90: right is down', points(rotated(BODY_RIGHT, 90, 0, 0), [0, -1, 0]))
check('roll 90: down is west', points(rotated(BODY_DOWN, 90, 0, 0), [0, 0, -1]))
check('roll 90: forward unchanged', points(rotated(BODY_FORWARD, 90, 0, 0), [1, 0, 0]))

// Pitching up lifts the nose and tips the belly forward
check('pitch 90: forward is up', points(rotated(BODY_FORWARD, 0, 90, 0), [0, 1, 0]))
check('pitch 90: down is north', points(rotated(BODY_DOWN, 0, 90, 0), [1, 0, 0]))
check('pitch 90: right unchanged', points(rotated(BODY_RIGHT, 0, 90, 0), [0, 0, 1]))

// A body fixed field turns with the vehicle, which is what keeps the arrow over its own section
const FIELD: Point3D = [0.4, -0.2, 0.9]
const heldStill = rotated(FIELD, 20, -10, 35)
check('a body fixed vector moves with the vehicle', `${heldStill}` !== `${toModelFrame(FIELD)}`)
const worldLength = Math.hypot(...heldStill)
check('rotation preserves length', Math.abs(worldLength - Math.hypot(...FIELD)) < 1e-6)

if (failures > 0) {
  throw new Error(`${failures} check(s) failed`)
}
console.log('\nall checks passed')
