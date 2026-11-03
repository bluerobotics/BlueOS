import { expect, Page, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

const PARAMETERS_TIMEOUT = 90_000

async function searchParameter(page: Page, name: string): Promise<void> {
  await expect(page.getByRole('row').nth(1)).toBeVisible({ timeout: PARAMETERS_TIMEOUT })
  await page.getByLabel('Search').fill(name)
  await expect(page.getByRole('cell', { name, exact: true })).toBeVisible()
}

test.describe('Autopilot Parameters', { tag: '@parameters' }, () => {
  test('Parameter editor loads the table and filters it', async ({ page, pageErrors }) => {
    test.setTimeout(PARAMETERS_TIMEOUT + 30_000)
    await page.goto('/vehicle/parameters')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Autopilot Parameters' })).toBeVisible()
    for (const header of ['Name', 'Description', 'Value']) {
      await expect(page.getByRole('columnheader', { name: header })).toBeVisible()
    }
    await searchParameter(page, 'SYSID_THISMAV')
    await expect(page.getByRole('button', { name: 'Save' })).toBeEnabled()
    await expect(page.getByRole('button', { name: 'Load' })).toBeEnabled()
    expect(pageErrors).toEqual([])
  })

  test('Parameter dialog opens and is cancelled', async ({ page, pageErrors }) => {
    test.setTimeout(PARAMETERS_TIMEOUT + 30_000)
    await page.goto('/vehicle/parameters')
    await searchParameter(page, 'SYSID_THISMAV')
    await page.getByRole('cell', { name: 'SYSID_THISMAV', exact: true }).click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('SYSID_THISMAV')).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Save', exact: true })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })

  test('Load parameter file dialog opens and is dismissed', async ({ page, pageErrors }) => {
    test.setTimeout(PARAMETERS_TIMEOUT + 30_000)
    await page.goto('/vehicle/parameters')
    await expect(page.getByRole('row').nth(1)).toBeVisible({ timeout: PARAMETERS_TIMEOUT })
    await page.getByRole('button', { name: 'Load' }).click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('Load parameter file')).toBeVisible()
    await expect(dialog.locator('.v-file-input')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
