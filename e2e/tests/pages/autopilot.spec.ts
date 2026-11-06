import { expect, Locator, Page, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

const KNOWN = /^\s*(?!Unknown)\S/

function boardInfo(page: Page, name: string): Locator {
  return page.locator('.row', { has: page.getByText(`${name}:`, { exact: true }) }).locator('.text-left')
}

test.describe('Autopilot Firmware', { tag: '@autopilot' }, () => {
  test('Autopilot page shows the board information', async ({ page, pageErrors }) => {
    await page.goto('/vehicle/autopilot')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Autopilot Firmware' })).toBeVisible()
    await expect(page.getByText('Autopilot', { exact: true })).toBeVisible()
    for (const name of ['Board name', 'Manufacturer', 'Mavlink platform']) {
      await expect(boardInfo(page, name)).toHaveText(KNOWN)
    }
    await expect(boardInfo(page, 'Vehicle type')).toHaveText(/^\s*(?!\s*Unknown)[\w ]+ \((?!Unknown)\w+\)\s*$/)
    await expect(boardInfo(page, 'Firmware version')).toHaveText(/^\s*\d+\.\d+\.\d+ \(\w+\)\s*$/)
    const sitl = (await boardInfo(page, 'Board name').textContent())?.trim() === 'SITL'
    await expect(page.getByRole('button', { name: 'SITL configuration' })).toHaveCount(sitl ? 1 : 0)
    if (sitl) {
      await expect(boardInfo(page, 'Mavlink platform')).toHaveText(/^\s*SITL_/)
    }
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Start autopilot', exact: true })).toBeEnabled()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Stop autopilot' })).toBeEnabled()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Restart autopilot' })).toBeEnabled()
    // DESTRUCTIVE – not exercised: re-enables the setup wizard
    await expect(page.locator('button:has(.mdi-wizard-hat)')).toBeVisible()
    expect(pageErrors).toEqual([])
  })

  test('Change board dialog opens and closes without applying', async ({ page, pageErrors }) => {
    await page.goto('/vehicle/autopilot')
    await page.getByRole('button', { name: 'Change board' }).click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('Change running board')).toBeVisible()
    await dialog.getByLabel('Available boards').click({ force: true })
    await expect(page.getByRole('option').first()).toBeVisible()
    await page.keyboard.press('Escape')
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Set' })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })

  test('Firmware update panel shows the upload options without installing', async ({ page, pageErrors }) => {
    await page.goto('/vehicle/autopilot')
    await expect(boardInfo(page, 'Board name')).toHaveText(KNOWN)
    await page.getByRole('button', { name: 'Firmware update' }).click()
    for (const option of ['Retrieve from Cloud', 'Upload firmware file', 'Restore default firmware']) {
      await expect(page.getByText(option)).toBeVisible()
    }
    await expect(page.getByLabel('Vehicle type')).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Install firmware' })).toBeDisabled()
    expect(pageErrors).toEqual([])
  })

  test('SITL configuration panel shows the frame without changing it', async ({ page, pageErrors }) => {
    await page.goto('/vehicle/autopilot')
    await expect(boardInfo(page, 'Board name')).toHaveText(KNOWN)
    const panel = page.getByRole('button', { name: 'SITL configuration' })
    test.skip(!(await panel.isVisible()), 'Board is not SITL')
    await panel.click()
    // DESTRUCTIVE – not exercised: changing the frame restarts SITL
    await expect(page.getByLabel('SITL frame')).toBeVisible()
    await expect(page.locator('.v-select', { has: page.getByLabel('SITL frame') }).locator('.v-select__selection')).not.toBeEmpty()
    expect(pageErrors).toEqual([])
  })
})
