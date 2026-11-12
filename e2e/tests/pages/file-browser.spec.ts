import { expect, test } from '@/fixtures/vehicle'

test('File browser lists the BlueOS folders', async ({ page }) => {
  await page.goto('/tools/file-browser')
  const files = page.frameLocator('iframe[title^="iframe-/file-browser/"]')
  await expect(files.getByRole('button', { name: 'configs', exact: true })).toBeVisible({ timeout: 30_000 })
})
