import { expect, test } from '@/fixtures/vehicle'

test('Dashboard shows the app cards', async ({ page }) => {
  await page.goto('/')
  for (const card of ['Autopilot Firmware', 'Vehicle Setup', 'Video Streams', 'Terminal']) {
    await expect(page.locator('.app-card').getByText(card, { exact: true })).toBeVisible()
  }
})
