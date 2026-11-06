import { expect, test } from '@/fixtures/recorded-test.fixture'
import { activeDialog } from '@/fixtures/vehicle'

test.describe.configure({ mode: 'serial' })

const STORE_LOADED = /No Extensions Available|not connected to the internet|Failed to fetch extension manifest/

test.describe('Extensions', { tag: '@extensions' }, () => {
  test('Extension store loads and opens the filter and sort menus', async ({ page, pageErrors }) => {
    await page.goto('/tools/extensions-manager')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Extensions Beta', exact: true })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Store' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'Installed' })).toBeVisible()
    const cards = page.getByRole('button', { name: /^(GET|INSTALLED|UPDATE)$/ })
    await expect(cards.or(page.getByText(STORE_LOADED)).first()).toBeVisible({ timeout: 60_000 })
    const total = await cards.count()
    if (total) {
      const search = page.getByPlaceholder('Search Extensions')
      await search.fill('no-extension-is-called-this')
      await expect(cards).toHaveCount(0)
      await search.fill('')
      await expect(cards).toHaveCount(total)
      await page.getByRole('button', { name: 'Filters' }).click()
      await expect(page.getByText('Clear', { exact: true })).toBeVisible()
      await page.keyboard.press('Escape')
      await page.getByRole('button', { name: 'Sort By' }).click()
      await expect(page.getByText('Popularity')).toBeVisible()
      await page.keyboard.press('Escape')
    }
    // DESTRUCTIVE – not exercised: UPDATE buttons on store cards
    expect(pageErrors).toEqual([])
  })

  test('Extension manifest dialog opens and is cancelled', async ({ page, pageErrors }) => {
    await page.goto('/tools/extensions-manager')
    await page.getByRole('main').locator('button:has(.mdi-cog)').click()
    const dialog = activeDialog(page)
    await expect(dialog.getByText('Extensions Manifest')).toBeVisible()
    await expect(dialog.getByText('Drag manifest sources to set priority.')).toBeVisible()
    // DESTRUCTIVE – not exercised
    await expect(dialog.getByRole('button', { name: 'Apply' })).toBeVisible()
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    expect(pageErrors).toEqual([])
  })

  test('Installed tab lists the installed extensions and opens the add menu', async ({ page, pageErrors }) => {
    const installed: { name: string, tag: string, docker: string, enabled: boolean }[] =
      await (await page.request.get('/kraken/v1.0/installed_extensions')).json()
    await page.goto('/tools/extensions-manager')
    await page.getByRole('tab', { name: 'Installed' }).click()
    if (!installed.length) {
      await expect(page.getByText('No Extensions installed.')).toBeVisible({ timeout: 60_000 })
    }
    for (const { name, tag, docker, enabled } of installed) {
      const card = page.locator('.v-card', { hasText: docker }).filter({ hasText: name }).last()
      await expect(card).toContainText(tag, { timeout: 60_000 })
      await expect(card.getByText(/^Up /)).toHaveCount(enabled ? 1 : 0)
    }
    // DESTRUCTIVE – not exercised: Uninstall, Update, Disable, Enable and start, Restart
    await page.locator('button:has(.mdi-plus)').click()
    await expect(page.locator('button:has(.mdi-file-upload-outline)')).toBeVisible()
    await expect(page.locator('button:has(.mdi-code-braces)')).toBeVisible()
    await page.locator('.v-btn--fab:has(.mdi-close)').click()
    await expect(page.locator('button:has(.mdi-code-braces)')).toBeHidden()
    expect(pageErrors).toEqual([])
  })
})
