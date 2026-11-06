import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('MAVLink Inspector', { tag: '@mavlink-inspector' }, () => {
  test('MAVLink inspector lists the message types and selects one', async ({ page, pageErrors }) => {
    await page.goto('/tools/mavlink-inspector')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'MAVLink Inspector' })).toBeVisible()
    await expect(page.getByLabel('Search')).toBeVisible()
    const heartbeat = page.getByText('HEARTBEAT', { exact: true })
    await expect(heartbeat).toBeVisible({ timeout: 30_000 })
    await heartbeat.click()
    await expect(page.locator('.v-virtual-scroll .v-list-item').first()).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
