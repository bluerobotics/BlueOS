// Moves the SITL calibration frame through MAVLink, like ArduPilot's Tools/mavproxy_modules/sitl_calibration.py:
// servo 5 picks the mode and servos 6, 7 and 8 carry roll, pitch and yaw
import { expect, Page } from '@playwright/test'

const STOP = 1000
const HOLD_ATTITUDE = 1150
const WALK_POSES = 1250
// Degrees, the frame creeps towards the asked attitude and a sample taken while it still turns is off the sphere
// the accelerometer fit expects
const ATTITUDE_TOLERANCE = 1
// A second still is enough for the calibration to take a sample
const SETTLE_TIME = 1_000
const SETTLE_TIMEOUT = 30_000

type Quaternion = [number, number, number, number]

function toPwm(degrees: number): number {
  return 1500 + Math.round(degrees * 500 / 180)
}

async function setServo(page: Page, channel: number, pwm: number): Promise<void> {
  const response = await page.request.post('/mavlink2rest/mavlink', {
    data: {
      header: { system_id: 255, component_id: 240, sequence: 0 },
      message: {
        type: 'COMMAND_LONG',
        param1: channel,
        param2: pwm,
        param3: 0,
        param4: 0,
        param5: 0,
        param6: 0,
        param7: 0,
        command: { type: 'MAV_CMD_DO_SET_SERVO' },
        target_system: 1,
        target_component: 1,
        confirmation: 0,
      },
    },
  })
  expect(response.ok(), `servo ${channel} should be set to ${pwm}`).toBeTruthy()
}

// Euler angles in radians, ZYX like ArduPilot
function quaternion(roll: number, pitch: number, yaw: number): Quaternion {
  const [cr, sr] = [Math.cos(roll / 2), Math.sin(roll / 2)]
  const [cp, sp] = [Math.cos(pitch / 2), Math.sin(pitch / 2)]
  const [cy, sy] = [Math.cos(yaw / 2), Math.sin(yaw / 2)]
  return [
    cr * cp * cy + sr * sp * sy,
    sr * cp * cy - cr * sp * sy,
    cr * sp * cy + sr * cp * sy,
    cr * cp * sy - sr * sp * cy,
  ]
}

function angleBetween(first: Quaternion, second: Quaternion): number {
  const dot = Math.abs(first.reduce((sum, value, index) => sum + value * second[index], 0))
  return 2 * Math.acos(Math.min(dot, 1)) * 180 / Math.PI
}

// The simulated attitude, the AHRS estimate is off while the sensors are not calibrated
async function attitude(page: Page): Promise<Quaternion> {
  const response = await page.request.get('/mavlink2rest/mavlink/vehicles/1/components/1/messages/SIMSTATE')
  const { roll, pitch, yaw } = (await response.json()).message
  return quaternion(roll, pitch, yaw)
}

// Degrees, the frame holds it until something else is asked
export async function setAttitude(page: Page, roll: number, pitch: number, yaw = 0): Promise<void> {
  await setServo(page, 6, toPwm(roll))
  await setServo(page, 7, toPwm(pitch))
  await setServo(page, 8, toPwm(yaw))
  await setServo(page, 5, HOLD_ATTITUDE)
  const wanted = quaternion(...[roll, pitch, yaw].map((degrees) => degrees * Math.PI / 180) as [number, number, number])
  let settledSince = Date.now()
  await expect(async () => {
    if (angleBetween(await attitude(page), wanted) > ATTITUDE_TOLERANCE) {
      settledSince = Date.now()
    }
    expect(Date.now() - settledSince, `the vehicle should hold roll ${roll} pitch ${pitch} yaw ${yaw}`)
      .toBeGreaterThan(SETTLE_TIME)
  }).toPass({ intervals: [200], timeout: SETTLE_TIMEOUT })
}

// The frame walks by itself through rotations around every axis, what the compass calibration needs
export async function walkPoses(page: Page): Promise<void> {
  await setServo(page, 5, WALK_POSES)
}

export async function stopMoving(page: Page): Promise<void> {
  await setServo(page, 5, STOP)
}
