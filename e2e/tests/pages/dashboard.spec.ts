import { expect, test } from '@/fixtures/vehicle'

test('Dashboard shows the app cards', async ({ page }) => {
  await page.goto('/')
  for (const card of ['Digital Twin', 'System Information', 'Ethernet Status', 'WiFi Status']) {
    await expect(page.getByTestId('home-card').getByText(card, { exact: true })).toBeVisible()
  }
})
