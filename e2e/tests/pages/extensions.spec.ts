import { expect, test } from '@/fixtures/vehicle'

test('Extensions page lists the installed extensions', async ({ page }) => {
  const installed: { docker: string }[] = await (await page.request.get('/kraken/v1.0/installed_extensions')).json()
  await page.goto('/tools/extensions-manager')
  await page.getByRole('tab', { name: 'Installed' }).click()
  const expected = installed.length ? installed[0].docker : 'No Extensions installed.'
  await expect(page.getByText(expected).first()).toBeVisible({ timeout: 60_000 })
})
