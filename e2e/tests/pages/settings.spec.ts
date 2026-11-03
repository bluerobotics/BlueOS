import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

test.describe('Settings', { tag: '@settings' }, () => {
  test('Settings page shows the controls of every section', async ({ page, pageErrors }) => {
    await page.goto('/settings')
    await expect(page.getByRole('heading', { name: 'Settings', level: 1 })).toBeVisible()
    for (const section of ['Appearance', 'Advanced Mode', 'Data Management', 'System']) {
      await expect(page.getByText(section, { exact: true })).toBeVisible()
    }
    for (const theme of ['Dark Theme', 'Light Theme']) {
      await expect(page.locator('.theme-card', { hasText: theme })).toBeVisible()
    }
    await expect(page.locator('.theme-card.selected-card .mdi-check-circle')).toHaveCount(1)
    // Global setup turns pirate mode on
    await expect(page.getByText('Enabled - Advanced features are visible')).toBeVisible()
    await expect(page.getByRole('switch')).toHaveCount(2)
    await expect(page.getByRole('switch').first()).toBeChecked()
    await expect(page.getByText(/^\s*\d+(\.\d+)? [kMG]?B\s*$/)).toHaveCount(2, { timeout: 30_000 })
    await expect(page.getByRole('button', { name: 'Download' })).toHaveCount(2)
    await expect(page.getByRole('button', { name: 'Download' }).first()).toBeEnabled()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Clear', exact: true })).toHaveCount(2)
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Run Wizard' })).toBeEnabled()
    // DESTRUCTIVE – not exercised
    await expect(page.getByRole('button', { name: 'Reset Settings' })).toBeEnabled()
    expect(pageErrors).toEqual([])
  })

  test('Clear logs dialog opens and is cancelled', async ({ page, pageErrors }) => {
    await page.goto('/settings')
    const clear = page.getByRole('button', { name: 'Clear', exact: true }).first()
    // The button only enables above 100 MB of service logs
    await expect(page.getByText(/^\s*\d+(\.\d+)? [kMG]?B\s*$/).first()).toBeVisible({ timeout: 30_000 })
    test.skip(!(await clear.isEnabled()), 'Service log folder is under 100 MB')
    await clear.click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('Clear system logs?')).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Clear logs' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })

  test('Reset settings dialog opens and is cancelled', async ({ page, pageErrors }) => {
    await page.goto('/settings')
    await page.getByRole('button', { name: 'Reset Settings' }).click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('WARNING')).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Yes, reset settings' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
