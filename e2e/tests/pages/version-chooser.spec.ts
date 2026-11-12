import { expect, test } from '@/fixtures/vehicle'

test('Version chooser shows the pirate mode sections', async ({ page }) => {
  await page.goto('/tools/version-chooser')
  for (const heading of ['Local Versions', 'Remote Versions', 'Manual Upload']) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible({ timeout: 30_000 })
  }
})
