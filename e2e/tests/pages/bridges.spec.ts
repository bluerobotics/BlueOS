import { expect, test } from '@/fixtures/vehicle'

test('Bridges page opens the new bridge dialog', async ({ page }) => {
  await page.goto('/tools/bridges')
  await page.locator('button:has(.mdi-plus)').click()
  await expect(page.getByText('New bridge')).toBeVisible()
  await expect(page.getByLabel('Serial port')).toBeVisible()
})
