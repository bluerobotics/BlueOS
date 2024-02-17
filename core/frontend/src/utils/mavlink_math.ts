// ported from https://github.com/ArduPilot/pymavlink/blob/master/mavextra.py#L60

import { Matrix3, Vector3, degrees } from "./math"

export function mag_heading(RawImu: Vector3, attitude: Vector3, declination: number) {
  // calculate heading from raw magnetometer
  let magX = RawImu.x
  let magY = RawImu.y
  let magZ = RawImu.z

  // go via a DCM matrix to match the APM calculation
  const dcmMatrix = (new Matrix3()).fromEuler(attitude.x, attitude.y, attitude.z)
  const cosPitchSqr = 1.0 - (dcmMatrix.e(6) * dcmMatrix.e(6))
  const headY = magY * dcmMatrix.e(8) - magZ * dcmMatrix.e(7)
  const headX = magX * cosPitchSqr - dcmMatrix.e(6) * (magY * dcmMatrix.e(7) + magZ * dcmMatrix.e(8))
  let heading = degrees(Math.atan2(-headY, headX)) + declination
  while (heading < -180) {
      heading += 360
  }
  return heading
}
