// Tests for the BlueOS Parameters page. They write SERVO_RATE and LOG_BITMASK on the vehicle and restore them.
// How to run: BLUEOS_URL=http://<ip> bun --cwd e2e e2e parameters.spec.ts
import { Locator, Page } from '@playwright/test'

import { expect, test } from '@/fixtures/vehicle'

// 5 seconds above the autopilot firmware test, the parameter list is slower to arrive
const BACKEND_TIMEOUT = 65_000

// Set by a scenario after it writes on the vehicle, so a failure still puts the original value back
let restore: ((page: Page) => Promise<void>) | undefined

async function waitParameters(page: Page): Promise<void> {
  // Save is only enabled once every parameter and its metadata are loaded
  await expect(page.getByTestId('parameters-download-button'), 'the parameters should load')
    .toBeEnabled({ timeout: BACKEND_TIMEOUT })
}

async function searchParameter(page: Page, search: string): Promise<void> {
  await page.getByTestId('parameter-search').fill(search)
  await expect(page.getByTestId('parameters-table').locator('mark').first(), `"${search}" should match something`)
    .toBeVisible()
}

function parameterRow(page: Page, name: string): Locator {
  const cell = page.getByTestId('parameter-name').filter({ hasText: new RegExp(`^\\s*${name}\\s*$`) })
  return page.getByRole('row').filter({ has: cell })
}

function parameterValue(page: Page, name: string): Locator {
  return parameterRow(page, name).getByTestId('parameter-value')
}

async function readValue(page: Page, name: string): Promise<number> {
  const value = parameterValue(page, name)
  await expect(value, `${name} should be listed`).toBeVisible()
  return parseFloat(await value.innerText())
}

async function openParameter(page: Page, name: string): Promise<void> {
  await parameterRow(page, name).click()
  await expect(page.getByTestId('parameter-save-button'), `the ${name} editor should open`).toBeVisible()
}

async function closeParameter(page: Page): Promise<void> {
  await page.keyboard.press('Escape')
  await expect(page.getByTestId('parameter-save-button'), 'the editor should close').toBeHidden()
}

async function reloadAndSearch(page: Page, search: string): Promise<void> {
  await page.reload()
  await waitParameters(page)
  await searchParameter(page, search)
}

// Vuetify draws its ripple over the checkbox input, so the click has to go through it
async function setChecked(checkbox: Locator, checked: boolean): Promise<void> {
  // A forced click does not wait for the editor to finish opening
  await (await checkbox.elementHandle())?.waitForElementState('stable')
  await checkbox.setChecked(checked, { force: true })
}

// Writes a number through the editor, bitmasks and options go through Custom
async function writeValue(page: Page, name: string, value: number): Promise<void> {
  await openParameter(page, name)
  const custom = page.getByTestId('parameter-custom-checkbox')
  if (await custom.count()) {
    await setChecked(custom, true)
  }
  await page.getByTestId('parameter-edit-input').fill(String(value))
  await page.getByTestId('parameter-save-button').click()
  await expect(page.getByTestId('parameter-save-button'), 'the editor should close after saving').toBeHidden()
}

function hertz(value: number): RegExp {
  return new RegExp(`^\\s*${value} \\[Hz\\]\\s*$`)
}

async function openSelect(page: Page, testId: string): Promise<Locator> {
  await page.getByTestId(testId).click()
  const menu = page.locator('.menuable__content__active')
  await expect(menu, `the ${testId} list should open`).toBeVisible()
  return menu
}

test.describe.serial('Parameters', () => {
  test.setTimeout(300_000)

  test.beforeEach(async ({ page }) => {
    await page.goto('/vehicle/parameters')
    await waitParameters(page)
  })

  test.afterEach(async ({ page }) => {
    if (restore) {
      await page.goto('/vehicle/parameters')
      await waitParameters(page)
      await restore(page)
      restore = undefined
    }
  })

  test('Scenario 1: SERVO_RATE survives a reload and is restored from a saved file', async ({ page }, testInfo) => {
    const name = 'SERVO_RATE'
    // SERVO without the V and the O, the fuzzy search should still find it
    const search = 'SER_rate'
    const value = parameterValue(page, name)
    const file = testInfo.outputPath('parameters.params')
    await test.step('save the parameters to a file', async () => {
      const download = page.waitForEvent('download')
      await page.getByTestId('parameters-download-button').click()
      await (await download).saveAs(file)
    })

    await searchParameter(page, search)
    const original = await readValue(page, name)
    const changed = original + 5

    await test.step(`change ${name} from ${original} to ${changed} Hz`, async () => {
      restore = async (current) => {
        await searchParameter(current, search)
        await writeValue(current, name, original)
      }
      await writeValue(page, name, changed)
      await expect(value, `${name} should show ${changed}`).toHaveText(hertz(changed), { timeout: BACKEND_TIMEOUT })
    })

    await test.step('the new value survives a reload', async () => {
      await reloadAndSearch(page, search)
      await expect(value, `${name} should still be ${changed}`).toHaveText(hertz(changed))
    })

    await test.step('load the saved file', async () => {
      await page.getByTestId('parameters-load-button').click()
      await page.getByTestId('parameters-file-input').setInputFiles(file)
      const loader = page.getByTestId('parameters-loader')
      await expect(loader, `${name} should be listed to be written`).toContainText(name)
      await page.getByTestId('parameters-write-button').click()
      await expect(page.getByTestId('parameters-write-success'), 'the parameters should be written')
        .toContainText('Parameters written successfully', { timeout: BACKEND_TIMEOUT })
      await page.getByTestId('parameters-loader-close-button').click()
    })

    await test.step('the original value is back after a reload', async () => {
      await reloadAndSearch(page, search)
      await expect(value, `${name} should be back to ${original}`).toHaveText(hertz(original))
      restore = undefined
    })
  })

  test('Scenario 2: LOG_BITMASK first option toggles, matches custom, and survives a reload', async ({ page }) => {
    const first = page.getByTestId('parameter-bitmask-option').first()
    const custom = page.getByTestId('parameter-custom-checkbox')
    const input = page.getByTestId('parameter-edit-input')
    const value = parameterValue(page, 'LOG_BITMASK')

    await searchParameter(page, 'log_bitmask')
    await openParameter(page, 'LOG_BITMASK')
    await expect(first, 'the bitmask options should be shown').toBeVisible()

    const name = await first.evaluate((option: HTMLInputElement) => option.labels?.[0]?.innerText.trim() ?? '')
    expect(name, 'the first bitmask option should have a name').not.toBe('')
    const enabled = await first.isChecked()
    const bit = Number(await first.inputValue())
    await setChecked(custom, true)
    const original = Number(await input.inputValue())
    const changed = enabled ? original - bit : original + bit

    await test.step(`toggle ${name} ${enabled ? 'off' : 'on'} and check Custom`, async () => {
      await setChecked(custom, false)
      await setChecked(first, !enabled)
      await setChecked(custom, true)
      await expect(input, `Custom should show ${changed}`).toHaveValue(String(changed))
      restore = async (current) => {
        await searchParameter(current, 'log_bitmask')
        await writeValue(current, 'LOG_BITMASK', original)
      }
      await page.getByTestId('parameter-save-button').click()
      const shown = expect(value, `${name} should be ${enabled ? 'off' : 'on'}`)
      await (enabled ? shown.not : shown).toContainText(name, { timeout: BACKEND_TIMEOUT })
    })

    await test.step('the new value survives a reload', async () => {
      await reloadAndSearch(page, 'log_bitmask')
      const shown = expect(value, `${name} should still be ${enabled ? 'off' : 'on'}`)
      await (enabled ? shown.not : shown).toContainText(name)
    })

    await test.step('toggle it back and check the original value after a reload', async () => {
      await openParameter(page, 'LOG_BITMASK')
      await setChecked(first, enabled)
      await page.getByTestId('parameter-save-button').click()
      const shown = expect(value, `${name} should be ${enabled ? 'on' : 'off'} again`)
      await (enabled ? shown : shown.not).toContainText(name, { timeout: BACKEND_TIMEOUT })
      await reloadAndSearch(page, 'log_bitmask')
      await openParameter(page, 'LOG_BITMASK')
      await setChecked(custom, true)
      await expect(input, `LOG_BITMASK should be back to ${original}`).toHaveValue(String(original))
      await closeParameter(page)
      restore = undefined
    })
  })

  test('Scenario 3: AHRS_ORIENTATION lists Yaw180 and Roll90', async ({ page }) => {
    await searchParameter(page, 'AHRS_orientation')
    await openParameter(page, 'AHRS_ORIENTATION')
    const options = await openSelect(page, 'parameter-options-select')
    // Exact, Roll90Yaw180 should not count
    for (const name of ['Yaw180', 'Roll90']) {
      const option = options.getByRole('option', { name, exact: true })
      // The list only renders more items as it scrolls
      await expect(async () => {
        await options.evaluate((menu) => menu.scrollTo(0, menu.scrollHeight))
        await expect(option).toBeAttached({ timeout: 1000 })
      }, `the ${name} option should exist`).toPass({ timeout: BACKEND_TIMEOUT })
    }
    await page.keyboard.press('Escape')
    await closeParameter(page)
  })

  test('Scenario 4: SPEED_MAX shows m/s units', async ({ page }) => {
    await searchParameter(page, 'speed_max')
    // SPEED_MAX only exists on ArduRover
    test.skip(!await parameterRow(page, 'SPEED_MAX').count(), 'this firmware has no SPEED_MAX')
    await openParameter(page, 'SPEED_MAX')
    // The units are the suffix next to the value field
    await expect(page.getByTestId('parameter-edit-input').locator('..'), 'the value field should show m/s')
      .toContainText('m/s')
    await closeParameter(page)
  })
})
