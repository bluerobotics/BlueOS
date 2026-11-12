import { expect, test } from '@/fixtures/vehicle'

test('Log browser shows the autopilot logs table', async ({ page }) => {
  await page.goto('/vehicle/logs')
  await expect(page.getByText('Autopilot logs')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('columnheader', { name: 'Modified' })).toBeVisible()
})
