import { expect, test } from '@/fixtures/vehicle'

test('Video page lists the devices', async ({ page }) => {
  await page.goto('/vehicle/video-manager')
  await expect(page.getByText(/No video-devices available\.|Device Controls/).first()).toBeVisible({ timeout: 30_000 })
})
