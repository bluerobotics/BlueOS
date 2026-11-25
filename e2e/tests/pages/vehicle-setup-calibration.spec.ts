// Tests for the BlueOS calibration pages under Vehicle Setup. They change the board to SITL with the ArduSub
// calibration frame, a simulated vehicle that rotates to the attitude asked through its servo outputs, then put
// everything back.
// How to run: BLUEOS_URL=http://<ip> bun --cwd e2e e2e vehicle-setup-calibration.spec.ts
import { Locator, Page } from '@playwright/test'

import {
  BACKEND_TIMEOUT, changeBoard, currentVehicle, currentVersion, INSTALL_TIMEOUT, installFirmware, openAutopilot,
  openFirmwares, OriginalBoard, restartAutopilot, restartWith, restoreBoard, saveBoard, setSitlFrame, sitlFrame,
} from '@/fixtures/autopilot'
import {
  parameterValue, readParameter, readParameters, saveParameters, searchParameter, waitParameters, writeParameter,
  writeParameters,
} from '@/fixtures/parameters'
import { setAttitude, stopMoving, walkPoses } from '@/fixtures/sitl-calibration'
import { closeDialog, openSelect } from '@/fixtures/ui'
import { expect, preparePage, test } from '@/fixtures/vehicle'

// The calibration frame only follows servos 5 to 8 when nothing else drives them, so the two motors there move to 11
// and 12. The sensor errors come from ArduPilot's own autotest, the calibrations should find them back.
const SETUP = {
  SIM_GND_BEHAV: 0,
  SERVO5_FUNCTION: 0,
  SERVO6_FUNCTION: 0,
  SERVO7_FUNCTION: 0,
  SERVO8_FUNCTION: 0,
  SERVO11_FUNCTION: 37,
  SERVO12_FUNCTION: 38,
  COMPASS_AUTO_ROT: 0,
  SIM_DRIFT_SPEED: 0,
  SIM_BARO_RND: 0,
}
// Errors put into the simulated IMU for the calibration to find, the offsets it computes should match them.
// SITL is close to perfect without them, so a calibration that did nothing would still pass
const FAKE_GYRO_BIAS = { SIM_GYR1_BIAS_X: 0.01, SIM_GYR1_BIAS_Y: -0.02, SIM_GYR1_BIAS_Z: 0.005 }
const FAKE_ACCEL_BIAS = { SIM_ACC1_BIAS_X: 0.7, SIM_ACC1_BIAS_Y: -0.3, SIM_ACC1_BIAS_Z: 1.8 }
// Back to the defaults, so the page starts with accelerometers that need a calibration
const UNCALIBRATED_ACCEL = Object.fromEntries(['INS_ACC', 'INS_ACC2'].flatMap((prefix) =>
  ['X', 'Y', 'Z'].flatMap((axis) => [[`${prefix}OFFS_${axis}`, 0], [`${prefix}SCAL_${axis}`, 1]])))
// Everything the tests or the calibrations write, put back from the saved file at the end
const TOUCHED = /^(SIM_|SERVO\d+_FUNCTION|COMPASS_|INS_|AHRS_TRIM|BARO\d_GND|BARO_ALT_OFFSET)/

// Degrees, what ArduPilot's sitl_accelcal sends for each prompt
const ACCEL_POSES: [RegExp, number, number][] = [
  [/on a level surface/, 0, 0],
  [/on its left side/, -90, 0],
  [/on its right side/, 90, 0],
  [/with its nose down/, 0, -90],
  [/with its nose up/, 0, 90],
  [/on its back/, 180, 0],
]
// The compass calibration needs minutes of rotation on a Raspberry Pi
const COMPASS_TIMEOUT = 240_000
// The quick calibration rejects another one for 5 seconds
const CALIBRATION_COOLDOWN = 5_000
// kg/m³ and m/s², what ArduSub's SITL uses to turn depth into pressure (AP_Baro::SimpleUnderWaterAtmosphere)
const WATER_DENSITY = 1024
const GRAVITY = 9.80665
const HPA_PER_METER = WATER_DENSITY * GRAVITY / 100

let original: (OriginalBoard & { frame: string }) | undefined
let saved: Record<string, number> | undefined

async function openConfigure(page: Page, subtab: string, ready: string): Promise<void> {
  await page.goto(`/vehicle/setup/configure/${subtab}`)
  await expect(page.getByTestId(ready), `the ${subtab} page should load`).toBeVisible({ timeout: BACKEND_TIMEOUT })
}

// Waits for the next prompt, puts the vehicle there and confirms it
async function placeVehicle(page: Page, poses = ACCEL_POSES): Promise<RegExp> {
  const prompt = page.getByTestId('full-accel-calibration-prompt')
  let pose: [RegExp, number, number] | undefined
  let asked = ''
  await expect(async () => {
    asked = await prompt.innerText()
    pose = poses.find(([pattern]) => pattern.test(asked))
    expect(pose, `"${asked}" should ask for a pose`).toBeDefined()
  }, 'the vehicle should ask for a pose').toPass({ timeout: BACKEND_TIMEOUT })
  const [pattern, roll, pitch] = pose!
  await setAttitude(page, roll, pitch)
  await page.getByTestId('full-accel-calibration-next-button').click()
  // The prompt stays until the vehicle asks for something else, another Next before that sends the same pose again.
  // After the last pose the dialog closes and the prompt goes away, that counts as taken too
  await expect.poll(() => prompt.innerText({ timeout: 1000 }).catch(() => ''), {
    message: 'the vehicle should take the sample',
    timeout: BACKEND_TIMEOUT,
  }).not.toBe(asked)
  return pattern
}

async function startFullAccel(page: Page): Promise<void> {
  await openConfigure(page, 'accelerometer', 'full-accel-calibration-button')
  await page.getByTestId('full-accel-calibration-button').click()
  await page.getByTestId('full-accel-calibration-start-button').click()
}

// The calibration is full-compass-calibration or large-vehicle-calibration, both in their own panel
async function openCompassDialog(page: Page, calibration: string, title: string): Promise<Locator> {
  await openConfigure(page, 'compass', `${calibration}-panel`)
  await page.getByTestId(`${calibration}-panel`).click()
  await page.getByTestId(`${calibration}-button`).click()
  const opened = page.getByTestId(`${calibration}-dialog`)
  await expect(opened, `the ${title} dialog should open`).toBeVisible()
  await expect(opened.getByTestId('vehicle-coordinates'), 'the SITL GPS should give the coordinates')
    .toHaveText(/-?\d/, { timeout: BACKEND_TIMEOUT })
  return opened
}

function expectNear(value: number, expected: number, tolerance: number, name: string): void {
  expect(Math.abs(value - expected), `${name} should be ${expected}, got ${value}`).toBeLessThanOrEqual(tolerance)
}

function compassChips(page: Page): Locator {
  return page.getByTestId('compass-calibration-chip')
}

test.describe.serial('Vehicle Setup calibration', () => {
  test.setTimeout(300_000)

  test.beforeAll(async ({ browser }, testInfo) => {
    testInfo.setTimeout(INSTALL_TIMEOUT + BACKEND_TIMEOUT * 8)
    const page = await browser.newPage({ baseURL: testInfo.project.use.baseURL })
    await preparePage(page)
    await openAutopilot(page)
    const board = page.getByTestId('autopilot-board-name')
    const name = (await board.innerText()).trim()
    const originalBoard = await saveBoard(page, name)
    if (name !== 'SITL') {
      await changeBoard(page, /SITL|Software In The Loop/)
      await expect(board, 'the board should become SITL').toHaveText(/^\s*SITL\s*$/, { timeout: BACKEND_TIMEOUT })
    }
    original = { ...originalBoard, frame: await sitlFrame(page) }
    await setSitlFrame(page, 'calibration')
    if (await currentVehicle(page) !== 'ArduSub' || !(await currentVersion(page)).startsWith('4.7.')) {
      const firmwares = await openFirmwares(page, 'ArduSub')
      await firmwares.getByRole('option', { name: /^STABLE-4\.7\.\d+$/ }).first().click()
      await installFirmware(page)
    }
    await page.goto('/vehicle/parameters')
    await waitParameters(page)
    saved = Object.fromEntries(Object.entries(await saveParameters(page)).filter(([name]) => TOUCHED.test(name)))
    await writeParameters(page, SETUP)
    await restartAutopilot(page)
    await page.goto('/vehicle/parameters')
    await waitParameters(page)
    await setAttitude(page, 0, 0)
    await page.close()
  })

  test.afterAll(async ({ browser }, testInfo) => {
    testInfo.setTimeout(INSTALL_TIMEOUT + BACKEND_TIMEOUT * 8)
    if (!original) {
      return
    }
    const page = await browser.newPage({ baseURL: testInfo.project.use.baseURL })
    await preparePage(page)
    await stopMoving(page)
    if (saved) {
      await writeParameters(page, saved)
      await restartAutopilot(page)
    }
    await openAutopilot(page)
    await setSitlFrame(page, original.frame)
    await restoreBoard(page, original)
    await page.close()
  })

  test('Scenario 1: the gyroscope calibration finds the simulated bias', async ({ page }) => {
    await writeParameters(page, FAKE_GYRO_BIAS)
    await setAttitude(page, 0, 0)
    await openConfigure(page, 'gyroscope', 'gyro-calibrate-button')
    await page.getByTestId('gyro-calibrate-button').click()
    await expect(page.getByTestId('gyro-calibration-status'), 'the gyroscopes should calibrate')
      .toContainText('Calibration done.', { timeout: 30_000 })
    // mrad/s, the first IMU is the one with the bias
    const offsets = page.getByTestId('gyro-offsets').first()
    await expect(async () => {
      const values = (await offsets.innerText()).split(',').map(parseFloat)
      // The bias is in rad/s and the page shows mrad/s, the simulated gyroscopes are noisy
      expectNear(values[0], FAKE_GYRO_BIAS.SIM_GYR1_BIAS_X * 1000, 2, 'X')
      expectNear(values[1], FAKE_GYRO_BIAS.SIM_GYR1_BIAS_Y * 1000, 2, 'Y')
      expectNear(values[2], FAKE_GYRO_BIAS.SIM_GYR1_BIAS_Z * 1000, 2, 'Z')
    }, 'the offsets should show the bias').toPass({ timeout: BACKEND_TIMEOUT })
  })

  test('Scenario 2: calibrating the gyroscopes automatically is saved', async ({ page }) => {
    const showGyroCal = async (text: string) => {
      await page.goto('/vehicle/parameters')
      await waitParameters(page)
      await searchParameter(page, 'INS_GYR_CAL')
      await expect(parameterValue(page, 'INS_GYR_CAL'), `INS_GYR_CAL should be ${text}`).toHaveText(text)
    }
    await showGyroCal('Never')
    // The page writes with a PARAM_SET on its websocket, leaving before that goes out loses the write
    let written = false
    page.on('websocket', (socket) => socket.on('framesent', (frame) => {
      written ||= String(frame.payload).includes('"PARAM_SET"')
    }))
    await openConfigure(page, 'gyroscope', 'gyro-calibrate-button')
    const options = await openSelect(page, 'parameter-options-select')
    await options.getByRole('option', { name: 'Start-up only' }).click()
    await expect.poll(() => written, { message: 'INS_GYR_CAL should be written', timeout: BACKEND_TIMEOUT }).toBe(true)
    await expect(() => showGyroCal('Start-up only'), 'INS_GYR_CAL should be saved')
      .toPass({ timeout: BACKEND_TIMEOUT * 2 })
  })

  test('Scenario 3: the full accelerometer calibration goes through the six poses', async ({ page }) => {
    await writeParameters(page, { ...FAKE_ACCEL_BIAS, ...UNCALIBRATED_ACCEL })
    await openConfigure(page, 'accelerometer', 'full-accel-calibration-button')
    const uncalibrated = page.getByTestId('accelerometer-calibration').filter({ hasText: 'Needs calibration' })
    // The page reloads, the parameters take a while to arrive again
    await expect(uncalibrated.first(), 'the accelerometers should start uncalibrated')
      .toBeVisible({ timeout: BACKEND_TIMEOUT })
    await startFullAccel(page)
    const dialog = page.getByTestId('full-accel-calibration-dialog')
    const prompt = page.getByTestId('full-accel-calibration-prompt')

    await test.step('closing the dialog midway keeps the calibration going', async () => {
      await expect(prompt, 'it should ask for level first')
        .toContainText('Place the vehicle on a level surface', { timeout: BACKEND_TIMEOUT })
      await closeDialog(page, dialog, 'full-accel-calibration-title')
      await page.getByTestId('full-accel-calibration-button').click()
      await expect(prompt, 'the prompt should be kept').toContainText('Place the vehicle on a level surface')
    })

    const remaining = [...ACCEL_POSES]
    for (let step = 0; step < ACCEL_POSES.length; step++) {
      await test.step(`pose ${step + 1}`, async () => {
        const done = await placeVehicle(page, remaining)
        remaining.splice(remaining.findIndex(([pattern]) => pattern === done), 1)
      })
    }
    await setAttitude(page, 0, 0)
    // The dialog closes on success, the result is read from the page
    await expect(dialog, 'the dialog should close when it succeeds').toBeHidden({ timeout: BACKEND_TIMEOUT })
    await expect(uncalibrated, 'every accelerometer should be calibrated').toHaveCount(0, { timeout: BACKEND_TIMEOUT })
    const offsets = await readParameters(page, ['INS_ACCOFFS_X', 'INS_ACCOFFS_Y', 'INS_ACCOFFS_Z'])
    expectNear(offsets.INS_ACCOFFS_X, FAKE_ACCEL_BIAS.SIM_ACC1_BIAS_X, 0.1, 'INS_ACCOFFS_X')
    expectNear(offsets.INS_ACCOFFS_Y, FAKE_ACCEL_BIAS.SIM_ACC1_BIAS_Y, 0.1, 'INS_ACCOFFS_Y')
    expectNear(offsets.INS_ACCOFFS_Z, FAKE_ACCEL_BIAS.SIM_ACC1_BIAS_Z, 0.1, 'INS_ACCOFFS_Z')
  })

  test('Scenario 4: the quick accelerometer calibration', async ({ page }) => {
    await setAttitude(page, 0, 0)
    await openConfigure(page, 'accelerometer', 'quick-accel-calibration-button')
    await page.getByTestId('quick-accel-calibration-button').click()
    const quick = page.getByTestId('quick-accel-calibration-dialog')
    await page.getByTestId('quick-accel-calibration-start-button').click()
    await expect(page.getByTestId('quick-accel-calibration-success'), 'it should succeed')
      .toBeVisible({ timeout: 30_000 })
    await expect(quick, 'the dialog should close by itself').toBeHidden()
  })

  test('Scenario 5: the level horizon trims a small tilt', async ({ page }) => {
    const roll = 3
    await page.waitForTimeout(CALIBRATION_COOLDOWN)
    await setAttitude(page, roll, 0)
    const yaw = await readParameter(page, 'AHRS_TRIM_Z')
    await openConfigure(page, 'accelerometer', 'level-horizon-button')
    await page.getByTestId('level-horizon-button').click()
    const level = page.getByTestId('level-horizon-dialog')
    await expect(page.getByTestId('level-horizon-attitude'), 'the attitude should show').toContainText(/Roll: -?\d/)
    await page.getByTestId('level-horizon-calibrate-button').click()
    await expect(page.getByTestId('level-horizon-status'), 'it should succeed')
      .toContainText('Calibration finished', { timeout: 30_000 })
    await closeDialog(page, level, 'level-horizon-title')
    // The level horizon writes roll and pitch, yaw is kept as it was
    const trim = await readParameters(page, ['AHRS_TRIM_X', 'AHRS_TRIM_Y', 'AHRS_TRIM_Z'])
    expect(trim.AHRS_TRIM_X, `AHRS_TRIM_X should be ${roll} degrees`).toBeCloseTo(roll * Math.PI / 180, 2)
    expect(trim.AHRS_TRIM_Y, 'AHRS_TRIM_Y should be 0, there is no pitch').toBeCloseTo(0, 2)
    expect(trim.AHRS_TRIM_Z, 'AHRS_TRIM_Z should be kept').toBe(yaw)
    await writeParameters(page, { AHRS_TRIM_X: 0, AHRS_TRIM_Y: 0 })
  })

  test('Scenario 6: the full compass calibration, from uncalibrated to calibrated', async ({ page }) => {
    const uncalibrated: Record<string, number> = {}
    for (const index of ['', '2', '3']) {
      for (const axis of ['X', 'Y', 'Z']) {
        uncalibrated[`COMPASS_OFS${index}_${axis}`] = 0
        uncalibrated[`COMPASS_ODI${index}_${axis}`] = 0
      }
    }
    await writeParameters(page, uncalibrated)
    await setAttitude(page, 0, 0)
    await openConfigure(page, 'compass', 'full-compass-calibration-panel')
    await expect(compassChips(page).first(), 'the compasses should need calibration')
      .toHaveText('Calibration Needed', { timeout: BACKEND_TIMEOUT })

    const compass = await openCompassDialog(page, 'full-compass-calibration', 'Onboard Compass Calibration')
    const checkboxes = compass.getByTestId('compass-mask-checkbox')
    await expect(checkboxes, 'the three compasses that can be calibrated should be listed').toHaveCount(3)
    await page.getByTestId('full-compass-calibration-calibrate-button').click()
    await expect(page.getByTestId('full-compass-calibration-instructions'), 'it should start')
      .toContainText('Spin your vehicle around all of its axes')
    await walkPoses(page)
    await expect(page.getByTestId('full-compass-calibration-progress'), 'the progress should show')
      .toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('full-compass-calibration-fitness'), 'every compass should report its fitness')
      .toHaveCount(3, { timeout: COMPASS_TIMEOUT })
    await setAttitude(page, 0, 0)
    // The simulated compasses are perfect, their off-diagonals stay at 0 and the page calls that Quick
    await expect(compassChips(page).first(), 'the first compass should be calibrated')
      .toHaveText(/Calibrated/, { timeout: BACKEND_TIMEOUT })
    await expect(page.getByTestId('full-compass-calibration-status'), 'it should say it finished')
      .toContainText('Calibration finished', { timeout: 30_000 })
    await page.getByTestId('full-compass-calibration-dismiss-button').click()
    await expect(compass, 'the dialog should close').toBeHidden()
  })

  test('Scenario 7: cancelling the compass calibration', async ({ page }) => {
    await setAttitude(page, 0, 0)
    const compass = await openCompassDialog(page, 'full-compass-calibration', 'Onboard Compass Calibration')
    const calibrate = page.getByTestId('full-compass-calibration-calibrate-button')
    await calibrate.click()
    await page.getByTestId('full-compass-calibration-cancel-button').click()
    await expect(page.getByTestId('full-compass-calibration-status'), 'it should cancel')
      .toContainText('Calibration cancelled', { timeout: 30_000 })
    await page.getByTestId('full-compass-calibration-ok-button').click()
    await expect(calibrate, 'it should be ready again').toBeEnabled()
    await closeDialog(page, compass, 'full-compass-calibration-title')
  })

  test('Scenario 8: the large vehicle calibration while facing north, then a reboot', async ({ page }) => {
    await setAttitude(page, 0, 0, 0)
    const large = await openCompassDialog(page, 'large-vehicle-calibration', 'Large Vehicle Compass Calibration')
    await page.getByTestId('large-vehicle-calibration-calibrate-button').click()
    await expect(page.getByTestId('large-vehicle-calibration-status'), 'it should succeed')
      .toContainText('Calibration finished', { timeout: 30_000 })
    await expect(compassChips(page).first(), 'the compass should have the quick calibration')
      .toHaveText('Calibrated (Quick)', { timeout: BACKEND_TIMEOUT })
    await restartWith(page, large.getByTestId('reboot-autopilot-button'))
    await openConfigure(page, 'compass', 'large-vehicle-calibration-panel')
    await expect(compassChips(page).first(), 'the calibration should survive the reboot')
      .toHaveText('Calibrated (Quick)', { timeout: BACKEND_TIMEOUT })
  })

  test('Scenario 9: compass learn is not offered on Sub 4.7', async ({ page }) => {
    await openConfigure(page, 'compass', 'compass-learn-panel')
    await page.getByTestId('compass-learn-panel').click()
    await expect(page.getByTestId('compass-learn-button'), 'it needs a GPS or DVL').toBeDisabled()
    await expect(page.getByTestId('compass-learn-unsupported'), 'the reason should show')
      .toHaveText(/Unsupported firmware \(4\.7\.\d+\)/)
  })

  test('Scenario 10: the barometer calibration', async ({ page }) => {
    // Readings are up to SIM_BARO_RND meters off each, so two can be twice that apart
    const tolerance = 2 * await readParameter(page, 'SIM_BARO_RND') * HPA_PER_METER
    await openConfigure(page, 'baro', 'baro-calibrate-button')
    const calibrate = page.getByTestId('baro-calibrate-button')
    await calibrate.click()
    await expect(page.getByTestId('baro-calibration-status'), 'it should succeed')
      .toContainText('Calibration done.', { timeout: 30_000 })
    await expect(calibrate, 'it can calibrate again').toBeEnabled()
    await expect(async () => {
      const pressure = parseFloat(await page.getByTestId('baro-pressure').first().innerText())
      const ground = parseFloat(await page.getByTestId('baro-ground-pressure').first().innerText())
      expect(Math.abs(pressure - ground), 'the ground pressure should be the current one')
        .toBeLessThanOrEqual(tolerance)
    }).toPass({ timeout: BACKEND_TIMEOUT })
  })

  test('Scenario 11: the full accelerometer calibration fails when a pose repeats', async ({ page }) => {
    await page.waitForTimeout(CALIBRATION_COOLDOWN)
    await startFullAccel(page)
    // Always the level pose, the second sample is too close to the first
    await placeVehicle(page, ACCEL_POSES.map(([pattern]) => [pattern, 0, 0]))
    await placeVehicle(page, ACCEL_POSES.map(([pattern]) => [pattern, 0, 0]))
    await expect(page.getByTestId('full-accel-calibration-prompt'), 'it should fail')
      .toContainText('Calibration Failed', { timeout: BACKEND_TIMEOUT })
    await page.getByTestId('full-accel-calibration-ok-button').click()
    await expect(page.getByTestId('full-accel-calibration-dialog'), 'Ok should close the dialog').toBeHidden()
  })

  test('Scenario 12: the quick accelerometer calibration fails while moving', async ({ page }) => {
    await page.waitForTimeout(CALIBRATION_COOLDOWN)
    await openConfigure(page, 'accelerometer', 'quick-accel-calibration-button')
    await walkPoses(page)
    await page.getByTestId('quick-accel-calibration-button').click()
    await page.getByTestId('quick-accel-calibration-start-button').click()
    await expect(page.getByTestId('quick-accel-calibration-failure'), 'it should say it failed')
      .toContainText(/Calibration failed/, { timeout: 15_000 })
  })

  test('Scenario 13: the level horizon fails past 10 degrees', async ({ page }) => {
    await page.waitForTimeout(CALIBRATION_COOLDOWN)
    await setAttitude(page, 20, 0)
    await openConfigure(page, 'accelerometer', 'level-horizon-button')
    await page.getByTestId('level-horizon-button').click()
    const calibrate = page.getByTestId('level-horizon-calibrate-button')
    await calibrate.click()
    await expect(page.getByTestId('level-horizon-status'), 'it should fail')
      .toContainText(/Calibration failed: .*MAV_RESULT_FAILED/, { timeout: 30_000 })
    await expect(calibrate, 'it can try again').toBeEnabled()
  })

  test('Scenario 14: the compass calibration fails with an impossible fit', async ({ page }) => {
    await writeParameter(page, 'COMPASS_CAL_FIT', 0.001)
    await openCompassDialog(page, 'full-compass-calibration', 'Onboard Compass Calibration')
    await page.getByTestId('full-compass-calibration-calibrate-button').click()
    await walkPoses(page)
    const status = page.getByTestId('full-compass-calibration-status')
    await expect(status, 'it should end')
      .toContainText(/Calibration failed|Calibration finished/, { timeout: COMPASS_TIMEOUT })
    await expect(status, 'it should not say it finished').toContainText('Calibration failed')
  })
})
