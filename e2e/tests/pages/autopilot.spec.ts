import { expect, test } from '@/fixtures/vehicle'

test('Autopilot page shows the board name', async ({ page }) => {
  await page.goto('/vehicle/autopilot')
  const board = page.locator('.row', { has: page.getByText('Board name:', { exact: true }) }).locator('.text-left')
  await expect(board).toHaveText(/^\s*(?!Unknown)\S/)
})
