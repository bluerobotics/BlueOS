import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Dashboard', { tag: '@dashboard' }, () => {
  test('Dashboard shows the app cards and no backend warning', async ({ page, pageErrors }) => {
    await page.goto('/')
    for (const card of ['Autopilot Firmware', 'Vehicle Setup', 'Video Streams', 'Terminal']) {
      await expect(page.locator('.app-card').getByText(card, { exact: true })).toBeVisible()
    }
    await expect(page.getByText('Disconnected', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('status')).toBeHidden()
    expect(pageErrors).toEqual([])
  })

  test('Unknown routes show the not found page', async ({ page, pageErrors }) => {
    await page.goto('/this-page-does-not-exist')
    await expect(page.getByText('Page not found!')).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
