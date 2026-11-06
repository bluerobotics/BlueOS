import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

test.describe('MAVLink Endpoints', { tag: '@endpoints' }, () => {
  test('Endpoints page lists the endpoints and opens the creation dialog', async ({ page, pageErrors }) => {
    await page.goto('/vehicle/endpoints')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'MAVLink Endpoints' })).toBeVisible()
    await expect(page.locator('.endpoint-card').or(page.getByText(/No endpoints available\.|Autopilot must be running/)).first())
      .toBeVisible({ timeout: 30_000 })
    const add = page.locator('button:has(.mdi-plus)')
    await expect(add).toBeVisible()
    if (await add.isEnabled()) {
      await add.click()
      const dialog = activeDialog(page)
      await expect(dialog.getByText('Endpoint', { exact: true })).toBeVisible()
      for (const field of ['Name', 'Owner', 'Type', 'IP/Device', 'Port/Baudrate']) {
        await expect(dialog.getByLabel(field, { exact: true })).toBeVisible()
      }
      // DESTRUCTIVE – not exercised
      await expect(dialog.getByRole('button', { name: 'Create endpoint' })).toBeVisible()
      await dialog.getByRole('button', { name: 'Cancel' }).click()
      await expect(dialog).toBeHidden()
    }
    // DESTRUCTIVE – not exercised: per-card switch, edit and trash buttons
    expect(pageErrors).toEqual([])
  })
})
