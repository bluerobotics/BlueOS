import { chromium, expect, FullConfig, Locator, Page } from '@playwright/test'

// The pirate mode tray id is reused by the two "reboot required" trays, so pick it by its icon
export const PIRATE_MODE_BUTTON = '#pirate-mode-tray-menu-button:has(.mdi-robot-happy, .mdi-skull-crossbones)'

// A fresh vehicle opens the persistent setup wizard on every page load until it is completed or aborted,
// and the guided tour once. Both are UI state, not vehicle configuration, so we answer the wizard
// check locally and skip the tour whenever it shows up, without writing anything to the vehicle
export async function tameOnboarding(page: Page): Promise<void> {
  await page.route('**/bag/v1.0/get/wizard', (route) => route.fulfill({ json: { version: 4 } }))
  await page.addLocatorHandler(page.getByRole('button', { name: 'Skip tour' }), (skip) => skip.click())
}

export async function setPirateMode(page: Page, enabled: boolean): Promise<void> {
  await page.goto('/')
  await page.locator(PIRATE_MODE_BUTTON).click()
  const toggle = page.getByRole('button', { name: /(Enable|Disable) Pirate Mode/ })
  await expect(toggle).toBeVisible()
  const wanted = enabled ? 'Enable Pirate Mode' : 'Disable Pirate Mode'
  if ((await toggle.textContent())?.includes(wanted)) {
    await toggle.click()
  } else {
    await page.keyboard.press('Escape')
  }
  await expect(page.locator(PIRATE_MODE_BUTTON).locator('.mdi-skull-crossbones')).toHaveCount(enabled ? 1 : 0)
}

export async function withBrowser(config: FullConfig, action: (page: Page) => Promise<void>): Promise<void> {
  const { baseURL, viewport } = config.projects[0].use
  const browser = await chromium.launch()
  const page = await browser.newPage({ baseURL, viewport })
  try {
    await tameOnboarding(page)
    await action(page)
  } finally {
    await browser.close()
  }
}

// The event log dialog is mounted eagerly, so the dialog role alone never resolves to the open one
export function activeDialog(page: Page): Locator {
  return page.getByRole('dialog').and(page.locator('.v-dialog__content--active'))
}
