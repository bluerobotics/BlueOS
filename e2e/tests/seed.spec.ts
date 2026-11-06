import { expect, test } from '@/fixtures/recorded-test.fixture'

test('BlueOS loads and shows the sidebar', async ({ page }) => {
  await page.goto('/')
  await expect(page.locator('.v-navigation-drawer')).toBeVisible()
  await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Vehicle Setup' })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath('sidebar.png') })
})
