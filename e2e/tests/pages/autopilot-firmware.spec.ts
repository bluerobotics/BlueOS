// Tests for the BlueOS Autopilot Firmware page. They change the board to SITL and install firmware on the vehicle.
// How to run: BLUEOS_URL=http://<ip> bun --cwd e2e e2e autopilot-firmware.spec.ts
import { Locator, Page } from '@playwright/test'

import { expect, test } from '@/fixtures/vehicle'

const BACKEND_TIMEOUT = 60_000
const INSTALL_TIMEOUT = 200_000
const VERSION = /\d+\.\d+\.\d+/
const VEHICLES = ['ArduSub', 'ArduRover', 'ArduCopter', 'ArduPlane'] as const

type Vehicle = typeof VEHICLES[number]

async function currentVehicle(page: Page): Promise<Vehicle> {
  const field = page.getByTestId('autopilot-vehicle-type')
  let vehicle: Vehicle | undefined
  await expect(async () => {
    const text = await field.innerText()
    vehicle = VEHICLES.find((name) => text.includes(`(${name})`))
    expect(vehicle, 'the vehicle type should show the firmware').toBeDefined()
  }).toPass({ timeout: BACKEND_TIMEOUT })
  return vehicle as Vehicle
}

async function currentVersion(page: Page): Promise<string> {
  const field = page.getByTestId('autopilot-firmware-version')
  await expect(field, 'the firmware version should be shown').toHaveText(VERSION, { timeout: BACKEND_TIMEOUT })
  return (await field.innerText()).match(VERSION)?.[0] ?? ''
}

async function expectVehicle(page: Page, vehicle: Vehicle): Promise<void> {
  await expect(page.getByTestId('autopilot-vehicle-type'), `Vehicle type should show ${vehicle}`)
    .toContainText(`(${vehicle})`, { timeout: BACKEND_TIMEOUT })
  await expect(page.getByTestId('autopilot-banner'), `the top banner should be the ${vehicle} one`)
    .toHaveAttribute('src', new RegExp(vehicle), { timeout: BACKEND_TIMEOUT })
}

async function openPanel(page: Page, testId: string): Promise<void> {
  const header = page.getByTestId(testId)
  if (await header.getAttribute('aria-expanded') !== 'true') {
    await header.click()
  }
}

async function openSelect(page: Page, testId: string): Promise<Locator> {
  const select = page.getByTestId(testId)
  await expect(select, `the ${testId} select should be enabled`).toBeEnabled({ timeout: BACKEND_TIMEOUT })
  await select.click()
  const menu = page.locator('.menuable__content__active')
  await expect(menu, `the ${testId} list should open`).toBeVisible()
  return menu
}

async function waitSerialsLoaded(page: Page): Promise<void> {
  const serials = await page.waitForResponse('**/ardupilot-manager/v1.0/serials', { timeout: BACKEND_TIMEOUT })
  await expect(page.getByTestId('serial-port-C'), 'the serial rows should be shown').toBeVisible()
  // With no serial configured the frontend keeps the rows loading forever
  if ((await serials.json()).length) {
    await expect(page.getByRole('main').getByRole('progressbar'), 'no serial row should be left loading')
      .toHaveCount(0, { timeout: BACKEND_TIMEOUT })
  }
}

async function selectVehicle(page: Page, vehicle: Vehicle): Promise<void> {
  await openPanel(page, 'firmware-update-panel')
  const vehicles = await openSelect(page, 'firmware-vehicle-select')
  // The select lists the vehicles without the Ardu prefix
  await vehicles.getByRole('option', { name: vehicle.replace('Ardu', ''), exact: true }).click()
}

// The list is sorted from the newest release, pick one of the two latest that is not the running one
async function selectStableFirmware(page: Page, running: string): Promise<string> {
  const firmwares = await openSelect(page, 'firmware-version-select')
  const stable = firmwares.getByRole('option', { name: /^STABLE-/ })
  await expect(stable.nth(1), 'at least two stable releases should be listed').toBeVisible()
  const latest = (await stable.allInnerTexts()).slice(0, 2).map((name) => name.trim())
  const name = latest.find((candidate) => candidate !== `STABLE-${running}`) ?? latest[0]
  await firmwares.getByRole('option', { name, exact: true }).click()
  return name.replace('STABLE-', '')
}

test.describe.serial('Autopilot Firmware', () => {
  test.setTimeout(300_000)

  test.beforeEach(async ({ page }) => {
    await page.goto('/vehicle/autopilot')
    await expect(page.getByTestId('autopilot-board-name'), 'the current board should be known')
      .toHaveText(/^\s*(?!Unknown)\S/, { timeout: BACKEND_TIMEOUT })
  })

  test('Precondition: the current board is SITL', async ({ page }) => {
    const board = page.getByTestId('autopilot-board-name')
    if ((await board.innerText()).trim() !== 'SITL') {
      await page.getByTestId('change-board-button').click()
      const boards = await openSelect(page, 'available-boards-select')
      await boards.getByRole('option', { name: /SITL|Software In The Loop/ }).click()
      await page.getByTestId('set-board-button').click()
    }
    await expect(board, 'the board should become SITL').toHaveText(/^\s*SITL\s*$/, { timeout: BACKEND_TIMEOUT })
    await openPanel(page, 'serial-configuration-panel')
    await waitSerialsLoaded(page)
  })

  test('Scenario 1: banner and vehicle type match the current firmware', async ({ page }) => {
    await expectVehicle(page, await currentVehicle(page))
  })

  test('Scenario 2: firmware list shows the vehicles and the stable versions', async ({ page }) => {
    const running = await currentVersion(page)
    await openPanel(page, 'firmware-update-panel')
    const vehicles = await openSelect(page, 'firmware-vehicle-select')
    for (const vehicle of ['Sub', 'Rover', 'Plane', 'Copter']) {
      const option = vehicles.getByRole('option', { name: vehicle, exact: true })
      await expect(option, `the ${vehicle} vehicle should be listed`).toBeVisible()
    }
    await vehicles.getByRole('option', { name: 'Sub', exact: true }).click()
    await selectStableFirmware(page, running)
    // Nothing is installed here
    await expect(page.getByTestId('install-firmware-button'), 'Install firmware should be available').toBeEnabled()
  })

  test('Scenario 3: the Vectored or Vectored 6DOF frame is available', async ({ page }) => {
    await openPanel(page, 'sitl-configuration-panel')
    const frames = await openSelect(page, 'sitl-frame-select')
    const vectored = frames.getByRole('option', { name: /^vectored(_6dof)?$/ })
    // The list only renders more items as it scrolls
    await expect(async () => {
      await frames.evaluate((menu) => menu.scrollTo(0, menu.scrollHeight))
      await expect(vectored.first()).toBeAttached({ timeout: 1000 })
    }, 'the vectored or vectored_6dof frame should exist').toPass({ timeout: BACKEND_TIMEOUT })
    await page.keyboard.press('Escape')
  })

  test('Scenario 4: a serial combobox lists the Navigator paths', async ({ page }) => {
    await openPanel(page, 'serial-configuration-panel')
    await waitSerialsLoaded(page)
    await page.getByTestId('serial-port-C').click()
    const navigatorPort = page.getByTestId('serial-port-option')
      .filter({ hasText: /\/dev\/ttyAMA\d+/ })
      .filter({ has: page.locator('[data-testid="device-path-image"][data*="navigator"]') })
    await expect(navigatorPort.first(), 'a ttyAMA* path with the Navigator image should be listed')
      .toBeVisible({ timeout: BACKEND_TIMEOUT })
    // Close without changing anything, Save and restart is not clicked
    await page.keyboard.press('Escape')
    await expect(navigatorPort.first(), 'the list should close').toBeHidden()
    await expect(page.getByTestId('serial-port-C'), 'the serial should not be changed').toHaveValue('')
  })

  test('Scenario 5: installs the firmware alternating vehicle and version', async ({ page }) => {
    // Anything that is not ArduSub, like ArduCopter or ArduPlane, goes back to ArduSub
    const target: Vehicle = await currentVehicle(page) === 'ArduSub' ? 'ArduRover' : 'ArduSub'
    const running = await currentVersion(page)

    await selectVehicle(page, target)
    const version = await selectStableFirmware(page, running)
    await page.getByTestId('install-firmware-button').click()

    const progress = page.getByTestId('install-firmware-progress')
    await expect(progress, 'the progress message should be shown').toBeVisible()
    await expect(progress, 'the install should finish').toBeHidden({ timeout: INSTALL_TIMEOUT })
    await expect(page.getByTestId('install-firmware-result'), 'the success message should be shown')
      .toContainText('Successfully installed new firmware')

    await expectVehicle(page, target)
    await expect(page.getByTestId('autopilot-firmware-version'), `the installed version should be ${version}`)
      .toContainText(version, { timeout: BACKEND_TIMEOUT })
  })
})
