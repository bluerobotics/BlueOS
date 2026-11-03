import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Log Browser', { tag: '@logs' }, () => {
  test('Log browser lists the autopilot logs and refreshes the list', async ({ page, pageErrors }) => {
    await page.goto('/vehicle/logs')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Log Browser' })).toBeVisible()
    await expect(page.getByText('Autopilot logs')).toBeVisible({ timeout: 30_000 })
    for (const header of ['Name', 'Size', 'Type', 'Modified', 'Actions']) {
      await expect(page.getByRole('columnheader', { name: header })).toBeVisible()
    }
    const logs = page.getByRole('row', { name: /\.(BIN|tlog) [\d.]+ [kMG]?B \.(BIN|tlog) \d{4}-\d{2}-\d{2}/ })
    const empty = page.getByText('No data available')
    await expect(logs.or(empty).first()).toBeVisible()
    // The footer only renders once the table has its items, so the count below is not a partial render
    await expect(page.getByText(/^\s*(1-\d+|0-0) of \d+\s*$/)).toBeVisible()
    const total = await logs.count()
    await page.locator('button:has(.mdi-update)').click()
    await expect(logs).toHaveCount(total)
    await expect(page.locator('button:has(.mdi-download-multiple)')).toBeDisabled()
    // DESTRUCTIVE – not exercised
    await expect(page.locator('button:has(.mdi-trash-can)')).toBeDisabled()
    expect(pageErrors).toEqual([])
  })
})
