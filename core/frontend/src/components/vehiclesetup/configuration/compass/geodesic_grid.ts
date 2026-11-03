/**
 * ArduPilot's AP_GeodesicGrid, as much of it as is needed to draw a MAG_CAL_PROGRESS completion
 * mask. The autopilot tessellates the icosahedron into 80 triangles, called sections, and reports
 * which ones it has collected magnetometer samples for.
 *
 * The tables and the section numbering below have to match libraries/AP_Math/AP_GeodesicGrid.h
 * exactly, since the section index is what indexes the bits of the completion mask.
 * Run `bun geodesic_grid.check.ts` to check them against ArduPilot's own test vectors.
 */

import * as THREE from 'three'

export type Point3D = [number, number, number]
export type Triangle3D = [Point3D, Point3D, Point3D]

const AP_GOLDEN_RATIO = (1 + Math.sqrt(5)) / 2

/** Radius of the sphere the icosahedron is inscribed in, so the length of every vertex vector. */
export const AP_GRID_RADIUS = Math.sqrt(1 + AP_GOLDEN_RATIO ** 2)

const AP_MIDPOINT_SCALE = AP_GRID_RADIUS / (2 * AP_GOLDEN_RATIO)

// T_0 to T_9, the remaining ten are their opposites
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

/**
 * The four sub-triangles of T = (a, b, c), in ArduPilot's order, so that section s = 4 * i + j is
 * the j-th sub-triangle of T_i. Midpoints are projected onto the sphere, which the autopilot has no
 * reason to do but makes the grid round when drawn. Scaling a vertex by a positive factor does not
 * change the sign of any coefficient in sectionByDirection, so the lookup is unaffected.
 */
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

export const AP_GEODESIC_SECTIONS = buildGeodesicSections()

function determinant([a0, a1, a2]: Point3D, [b0, b1, b2]: Point3D, [c0, c1, c2]: Point3D): number {
  return a0 * (b1 * c2 - b2 * c1) - b0 * (a1 * c2 - a2 * c1) + c0 * (a1 * b2 - a2 * b1)
}

/**
 * The section crossed by a direction, or -1 if there is none. A direction crosses a section when
 * all of its coefficients in the basis of that section's vertices are non-negative. Edges belong to
 * both of the sections that share them, and the first one found is returned.
 */
export function sectionByDirection(direction: Point3D): number {
  const eps = 1e-6
  // the null vector crosses no section, and it satisfies the test below for every one of them
  if (direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2 < eps) {
    return -1
  }
  for (const [section, [a, b, c]] of AP_GEODESIC_SECTIONS.entries()) {
    const det = determinant(a, b, c)
    if (Math.abs(det) < eps) {
      continue
    }
    const x = determinant(direction, b, c) / det
    const y = determinant(a, direction, c) / det
    const z = determinant(a, b, direction) / det
    if (x >= -eps && y >= -eps && z >= -eps) {
      return section
    }
  }
  return -1
}

/** Whether a section is set in a MAG_CAL_PROGRESS completion mask, which is 80 bits over 10 bytes. */
export function sectionCompleted(completion_mask: number[], section: number): boolean {
  const byte = completion_mask[Math.floor(section / 8)] ?? 0
  return (byte & 1 << section % 8) !== 0
}

/**
 * ArduPilot works in body frame (x forward, y right, z down), while three.js is y-up, so the grid
 * is drawn with forward on x, right on z and up on y. Only what gets drawn is rotated into the
 * model frame, so that section lookups stay in body frame and their indices keep matching the
 * completion mask. The vehicle models are y-up but face +z, they are turned onto forward when loaded.
 */
export function toModelFrame([x, y, z]: Point3D): Point3D {
  return [x, -z, y]
}

/** toModelFrame as a rotation, which is what it is: a quarter turn about the forward axis. */
const MODEL_FROM_BODY = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), Math.PI / 2)

/**
 * The vehicle's attitude, as a rotation to apply to everything drawn in the model frame. The grid is
 * body fixed, so rotating it along with the vehicle leaves the field pointing the same way in the
 * world while the vehicle turns underneath it.
 *
 * ATTITUDE is the aerospace 3-2-1 sequence taking body frame to NED, which three.js spells 'ZYX'.
 * Conjugating it by MODEL_FROM_BODY re-expresses it in the y-up frame the grid is drawn in, so north
 * ends up along x, east along z and up along y.
 */
export function modelRotationFromAttitude(roll: number, pitch: number, yaw: number): THREE.Quaternion {
  const bodyToNed = new THREE.Quaternion().setFromEuler(new THREE.Euler(roll, pitch, yaw, 'ZYX'))
  return MODEL_FROM_BODY.clone().multiply(bodyToNed).multiply(MODEL_FROM_BODY.clone().invert())
}
