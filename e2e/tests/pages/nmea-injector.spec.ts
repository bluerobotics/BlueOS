import { expect, test } from '@/fixtures/vehicle'

test('NMEA injector page opens the new socket dialog', async ({ page }) => {
  await page.goto('/tools/nmea-injector')
  await page.locator('button:has(.mdi-plus)').click()
  await expect(page.getByText('New NMEA socket')).toBeVisible()
  await expect(page.getByLabel('Socket port')).toHaveValue(/^\d+$/)
})
