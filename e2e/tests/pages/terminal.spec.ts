import { expect, test } from '@/fixtures/vehicle'

test('Terminal page renders the web terminal', async ({ page }) => {
  await page.goto('/tools/web-terminal')
  const terminal = page.frameLocator('iframe[title="iframe-/terminal/"]')
  await expect(terminal.locator('.xterm-screen canvas').first()).toBeVisible()
})
