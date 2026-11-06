import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('File Browser', { tag: '@file-browser' }, () => {
  test('File browser lists the BlueOS folders and opens one', async ({ page, pageErrors }) => {
    await page.goto('/tools/file-browser')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'File Browser' })).toBeVisible()
    // DESTRUCTIVE – not exercised: the frame contents can delete and edit files
    const files = page.frameLocator('iframe[title^="iframe-/file-browser/"]')
    for (const folder of ['ardupilot_logs', 'configs', 'extensions', 'system_logs', 'userdata']) {
      await expect(files.getByRole('button', { name: folder, exact: true })).toBeVisible({ timeout: 30_000 })
    }
    await files.getByRole('button', { name: 'configs', exact: true }).dblclick()
    await expect(files.getByRole('button', { name: 'bag-of-holding', exact: true })).toBeVisible()
    expect(pageErrors).toEqual([])
  })
})
