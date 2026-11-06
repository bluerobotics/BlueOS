import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

test.describe('Serial Bridges', { tag: '@bridges' }, () => {
  test('Serial bridges page opens the new bridge dialog and switches modes', async ({ page, pageErrors }) => {
    await page.goto('/tools/bridges')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Serial Bridges' })).toBeVisible()
    const bridges = page.getByRole('main').getByText(/\/dev\//)
    const empty = page.getByText('No bridges available. You can add a serial to UDP bridge by clicking the + symbol')
    await expect(bridges.or(empty).first()).toBeVisible()
    await page.locator('button:has(.mdi-plus)').click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('New bridge')).toBeVisible()
    await expect(dialog.getByLabel('Serial port')).toBeVisible()
    await dialog.locator('.v-select', { has: page.getByLabel('Serial baudrate') }).locator('.v-select__slot').click()
    await expect(page.getByRole('option', { name: '115200', exact: true })).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(dialog.getByText(/Server mode will bind to the given port/)).toBeVisible()
    await expect(dialog.getByLabel('IP address (Server mode)')).toBeVisible()
    await expect(dialog.getByLabel('Vehicle/Server port')).toHaveValue(/^\d+$/)
    await dialog.getByRole('tab', { name: 'Client Mode' }).click()
    await expect(dialog.getByLabel('Topside/Target port')).toBeVisible()
    await dialog.getByRole('tab', { name: 'Server Mode' }).click()
    await expect(dialog.getByLabel('Topside/Target port')).toBeHidden()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Create' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
