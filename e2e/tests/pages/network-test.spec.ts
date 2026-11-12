import { expect, test } from '@/fixtures/vehicle'

test('Network test page measures the latency', async ({ page }) => {
  await page.goto('/tools/network-test')
  const local = page.locator('.v-card', { hasText: 'Local Network Speed and Latency Test' }).last()
  await expect(local.getByText(/\d+ ms/)).toBeVisible()
})
