import { expect, test } from '@/fixtures/vehicle'

test('Vehicle setup overview shows the flight controller', async ({ page }) => {
  test.setTimeout(120_000)
  await page.goto('/vehicle/setup')
  await expect(page.getByRole('row', { name: /^Flight Controller \S+/ })).toBeVisible({ timeout: 90_000 })
})
