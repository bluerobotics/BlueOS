import { expect, test } from '@/fixtures/vehicle'

test('Autopilot page shows the board name', async ({ page }) => {
  await page.goto('/vehicle/autopilot')
  await expect(page.getByTestId('autopilot-board-name')).toHaveText(/^\s*(?!Unknown)\S/)
})
