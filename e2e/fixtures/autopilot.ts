import { expect, Locator, Page } from '@playwright/test'

import { BACKEND_TIMEOUT, openSelect } from '@/fixtures/ui'

export { BACKEND_TIMEOUT }

export const INSTALL_TIMEOUT = 200_000
const VERSION = /\d+\.\d+\.\d+/
const VEHICLES = ['ArduSub', 'ArduRover', 'ArduCopter', 'ArduPlane'] as const

export type Vehicle = typeof VEHICLES[number]
// Each board keeps its own firmware and parameters, so only SITL needs its vehicle and version back
export type OriginalBoard = { board: string, vehicle?: Vehicle, version?: string }

export async function currentVehicle(page: Page): Promise<Vehicle> {
  const field = page.getByTestId('autopilot-vehicle-type')
  let vehicle: Vehicle | undefined
  await expect(async () => {
    const text = await field.innerText()
    vehicle = VEHICLES.find((name) => text.includes(`(${name})`))
    expect(vehicle, 'the vehicle type should show the firmware').toBeDefined()
  }).toPass({ timeout: BACKEND_TIMEOUT })
  return vehicle as Vehicle
}

export async function currentVersion(page: Page): Promise<string> {
  const field = page.getByTestId('autopilot-firmware-version')
  await expect(field, 'the firmware version should be shown').toHaveText(VERSION, { timeout: BACKEND_TIMEOUT })
  return (await field.innerText()).match(VERSION)?.[0] ?? ''
}

export async function expectVehicle(page: Page, vehicle: Vehicle): Promise<void> {
  await expect(page.getByTestId('autopilot-vehicle-type'), `Vehicle type should show ${vehicle}`)
    .toContainText(`(${vehicle})`, { timeout: BACKEND_TIMEOUT })
  await expect(page.getByTestId('autopilot-banner'), `the top banner should be the ${vehicle} one`)
    .toHaveAttribute('src', new RegExp(vehicle), { timeout: BACKEND_TIMEOUT })
}

export async function openPanel(page: Page, testId: string): Promise<void> {
  const header = page.getByTestId(testId)
  if (await header.getAttribute('aria-expanded') !== 'true') {
    await header.click()
  }
}

export async function waitSerialsLoaded(page: Page): Promise<void> {
  const serials = await page.waitForResponse('**/ardupilot-manager/v1.0/serials', { timeout: BACKEND_TIMEOUT })
  await expect(page.getByTestId('serial-port-C'), 'the serial rows should be shown').toBeVisible()
  // With no serial configured the frontend keeps the rows loading forever
  if ((await serials.json()).length) {
    await expect(page.getByRole('main').getByRole('progressbar'), 'no serial row should be left loading')
      .toHaveCount(0, { timeout: BACKEND_TIMEOUT })
  }
}

export async function selectVehicle(page: Page, vehicle: Vehicle): Promise<void> {
  await openPanel(page, 'firmware-update-panel')
  const vehicles = await openSelect(page, 'firmware-vehicle-select')
  // The select lists the vehicles without the Ardu prefix
  await vehicles.getByRole('option', { name: vehicle.replace('Ardu', ''), exact: true }).click()
}

// The list is sorted from the newest release, pick one of the two latest that is not the running one
export async function selectStableFirmware(page: Page, running: string): Promise<string> {
  const firmwares = await openSelect(page, 'firmware-version-select')
  const stable = firmwares.getByRole('option', { name: /^STABLE-/ })
  await expect(stable.nth(1), 'at least two stable releases should be listed').toBeVisible()
  const latest = (await stable.allInnerTexts()).slice(0, 2).map((name) => name.trim())
  const name = latest.find((candidate) => candidate !== `STABLE-${running}`) ?? latest[0]
  await firmwares.getByRole('option', { name, exact: true }).click()
  return name.replace('STABLE-', '')
}

export async function changeBoard(page: Page, board: RegExp | string): Promise<void> {
  await page.getByTestId('change-board-button').click()
  const boards = await openSelect(page, 'available-boards-select')
  await boards.getByRole('option', { name: board, exact: true }).click()
  await page.getByTestId('set-board-button').click()
}

export async function installFirmware(page: Page): Promise<void> {
  await page.getByTestId('install-firmware-button').click()
  const progress = page.getByTestId('install-firmware-progress')
  await expect(progress, 'the progress message should be shown').toBeVisible()
  await expect(progress, 'the install should finish').toBeHidden({ timeout: INSTALL_TIMEOUT })
  await expect(page.getByTestId('install-firmware-result'), 'the success message should be shown')
    .toContainText('Successfully installed new firmware')
}

export async function openAutopilot(page: Page): Promise<void> {
  await page.goto('/vehicle/autopilot')
  await expect(page.getByTestId('autopilot-board-name'), 'the current board should be known')
    .toHaveText(/^\s*(?!Unknown)\S/, { timeout: BACKEND_TIMEOUT })
}

export async function sitlFrame(page: Page): Promise<string> {
  await openPanel(page, 'sitl-configuration-panel')
  const select = page.getByTestId('sitl-frame-select')
  await expect(select, 'the SITL frame should be known').toBeEnabled({ timeout: BACKEND_TIMEOUT })
  return (await page.getByTestId('sitl-frame-selection').innerText()).trim()
}

export async function setSitlFrame(page: Page, frame: string): Promise<void> {
  if (await sitlFrame(page) === frame) {
    return
  }
  const frames = await openSelect(page, 'sitl-frame-select')
  const option = frames.getByRole('option', { name: frame, exact: true })
  // The list only renders more items as it scrolls
  await expect(async () => {
    await frames.evaluate((menu) => menu.scrollTo(0, menu.scrollHeight))
    await expect(option).toBeAttached({ timeout: 1000 })
  }, `the ${frame} frame should exist`).toPass({ timeout: BACKEND_TIMEOUT })
  await option.click()
  await expect(page.getByText('SITL frame set, autopilot restarted'), 'the autopilot should restart')
    .toBeVisible({ timeout: BACKEND_TIMEOUT })
}

// The click that restarts, from the Autopilot page or a Reboot Autopilot button
export async function restartWith(page: Page, button: Locator): Promise<void> {
  const restarted = page.waitForResponse(
    (response) => response.request().method() === 'POST' && response.url().endsWith('/restart'),
    { timeout: BACKEND_TIMEOUT },
  )
  await button.click()
  expect((await restarted).ok(), 'the autopilot should restart').toBeTruthy()
}

export async function restartAutopilot(page: Page): Promise<void> {
  await openAutopilot(page)
  await restartWith(page, page.getByTestId('restart-autopilot-button'))
}

export async function saveBoard(page: Page, board: string): Promise<OriginalBoard> {
  if (board !== 'SITL') {
    return { board }
  }
  return { board, vehicle: await currentVehicle(page), version: await currentVersion(page) }
}

export async function restoreBoard(page: Page, original: OriginalBoard): Promise<void> {
  const board = page.getByTestId('autopilot-board-name')
  if ((await board.innerText()).trim() !== original.board) {
    await changeBoard(page, original.board)
    await expect(board, `the board should be back to ${original.board}`)
      .toHaveText(original.board, { timeout: BACKEND_TIMEOUT })
  }
  const { vehicle, version } = original
  if (!vehicle || !version) {
    return
  }
  if (await currentVehicle(page) === vehicle && await currentVersion(page) === version) {
    return
  }
  await selectVehicle(page, vehicle)
  const firmwares = await openSelect(page, 'firmware-version-select')
  await firmwares.getByRole('option', { name: `STABLE-${version}`, exact: true }).click()
  await installFirmware(page)
  await expectVehicle(page, vehicle)
}
