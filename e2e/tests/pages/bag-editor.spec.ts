import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Bag Editor', { tag: '@bag-editor' }, () => {
  test('Bag editor loads the database and switches between code and tree mode', async ({ page, pageErrors }) => {
    const keys = Object.keys(await (await page.request.get('/bag/v1.0/get/*')).json())
    expect(keys.length).toBeGreaterThan(0)
    await page.goto('/tools/bag-editor')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Bag Editor' })).toBeVisible()
    const editor = page.locator('.jsoneditor')
    await expect(editor).toHaveClass(/jsoneditor-mode-code/)
    await expect(editor.locator('.ace_content')).toContainText(`"${keys[0]}": {`)
    await page.locator('button:has(.mdi-file-tree)').click()
    await expect(editor).toHaveClass(/jsoneditor-mode-tree/)
    for (const key of keys) {
      await expect(editor.locator('.jsoneditor-field', { hasText: new RegExp(`^${key}$`) }).first()).toBeVisible()
    }
    await page.locator('button:has(.mdi-text-long)').click()
    await expect(editor).toHaveClass(/jsoneditor-mode-code/)
    await expect(editor.locator('.ace_content')).toContainText(`"${keys[0]}": {`)
    // DESTRUCTIVE – not exercised
    await expect(page.locator('button:has(.mdi-content-save-check-outline)')).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
