// ported from https://github.com/ArduPilot/pymavlink/blob/master/mavextra.py#L60

import { glMatrix, vec3, mat3 } from 'gl-matrix'

export default function mag_heading(RawImu: vec3, attitude: vec3, declination: number): number {
  // calculate heading from raw magnetometer
  const magX = RawImu[0]
  const magY = RawImu[1]
  const magZ = RawImu[2]

  // go via a DCM matrix to match the APM calculation
  const dcmMatrix = mat3.fromEuler(mat3.create(), attitude[0], attitude[1], attitude[2])
  const cosPitchSqr = 1.0 - dcmMatrix[6] * dcmMatrix[6]
  const headY = magY * dcmMatrix[8] - magZ * dcmMatrix[7]
  const headX = magX * cosPitchSqr - dcmMatrix[6] * (magY * dcmMatrix[7] + magZ * dcmMatrix[8])
  let heading = glMatrix.toDegree(Math.atan2(-headY, headX)) + declination
  while (heading < -180) {
    heading += 360
  }
  return heading
}
