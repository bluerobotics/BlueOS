import { expect, test } from '@/fixtures/vehicle'

test('Bag editor switches to tree mode', async ({ page }) => {
  await page.goto('/tools/bag-editor')
  const editor = page.locator('.jsoneditor')
  await expect(editor).toHaveClass(/jsoneditor-mode-code/)
  await page.locator('button:has(.mdi-file-tree)').click()
  await expect(editor).toHaveClass(/jsoneditor-mode-tree/)
})
