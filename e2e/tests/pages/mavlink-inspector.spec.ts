import { expect, test } from '@/fixtures/vehicle'

test('MAVLink inspector lists the heartbeat message', async ({ page }) => {
  await page.goto('/tools/mavlink-inspector')
  await expect(page.getByText('HEARTBEAT', { exact: true })).toBeVisible({ timeout: 30_000 })
})
