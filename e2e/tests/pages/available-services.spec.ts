import { expect, test } from '@/fixtures/vehicle'

test('Available services page lists the services', async ({ page }) => {
  await page.goto('/tools/available-services')
  await expect(page.getByRole('columnheader', { name: 'Service Name' })).toBeVisible()
  await expect(page.getByRole('row').nth(1)).toBeVisible()
})
