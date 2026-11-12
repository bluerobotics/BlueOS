import { expect, test } from '@/fixtures/vehicle'

test('Settings page shows pirate mode enabled', async ({ page }) => {
  await page.goto('/settings')
  await expect(page.getByText('Enabled - Advanced features are visible')).toBeVisible()
})
