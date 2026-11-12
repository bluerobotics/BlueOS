import { expect, test } from '@/fixtures/vehicle'

test('Parameter editor filters the table', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/vehicle/parameters')
  // The table only fills once every parameter is fetched from the autopilot
  await expect(page.getByRole('row').nth(1)).toBeVisible({ timeout: 90_000 })
  await page.getByLabel('Search').fill('SYSID_THISMAV')
  await expect(page.getByRole('cell', { name: 'SYSID_THISMAV', exact: true })).toBeVisible()
})
