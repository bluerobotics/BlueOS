import { expect, test } from '@/fixtures/vehicle'

test('Endpoints page lists the endpoints', async ({ page }) => {
  await page.goto('/vehicle/endpoints')
  const empty = page.getByText(/No endpoints available\.|Autopilot must be running/)
  await expect(page.locator('.endpoint-card').or(empty).first()).toBeVisible({ timeout: 30_000 })
})
