import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Available Services', { tag: '@available-services' }, () => {
  test('Available services page lists the service table', async ({ page, pageErrors }) => {
    await page.goto('/tools/available-services')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Available Services' })).toBeVisible()
    await expect(page.getByText('Shows all available services running on BlueOS')).toBeVisible()
    for (const header of ['Port', 'Service Name', 'Webpage', 'API Documentation', 'Versions']) {
      await expect(page.getByRole('columnheader', { name: header })).toBeVisible()
    }
    await expect(page.getByRole('row').nth(1)).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
