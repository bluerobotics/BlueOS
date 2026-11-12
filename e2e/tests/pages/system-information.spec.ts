import { expect, test } from '@/fixtures/vehicle'

test('System information page lists the processes', async ({ page }) => {
  await page.goto('/tools/system-information')
  await page.getByRole('tab', { name: 'Processes' }).click()
  await expect(page.getByRole('columnheader', { name: /^PID/ })).toBeVisible()
})
