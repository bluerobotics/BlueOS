import { expect, test } from '@/fixtures/recorded-test.fixture'

test.describe.configure({ mode: 'serial' })

test.describe('Terminal', { tag: '@terminal' }, () => {
  test('Terminal page connects the web terminal', async ({ page, pageErrors }) => {
    const socket = page.waitForEvent('websocket', (websocket) => websocket.url().includes('/terminal/ws'))
    await page.goto('/tools/web-terminal')
    await expect(page.locator('.v-navigation-drawer').getByRole('link', { name: 'Terminal' })).toBeVisible()
    // The shell output arrives over the websocket and is painted on a canvas, so the frame has no text to read
    await (await socket).waitForEvent('framereceived')
    // DESTRUCTIVE – not exercised: the frame is a shell
    const terminal = page.frameLocator('iframe[title="iframe-/terminal/"]')
    await expect(terminal.locator('.xterm-screen canvas').first()).toBeVisible()
    await expect(terminal.getByLabel('Terminal input')).toBeAttached()
    expect(pageErrors).toEqual([])
  })
})
