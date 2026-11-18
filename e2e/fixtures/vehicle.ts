import { expect, Page, test as base } from '@playwright/test'

// Also used by hooks that open their own page, like afterAll
export async function preparePage(page: Page): Promise<void> {
  // Pirate mode and the language are frontend settings stored in the bag of holding, so the answer is
  // patched locally and nothing is written on the vehicle
  await page.route('**/bag/v1.0/get/settings/settings_version', (route) => route.fulfill({ json: 1 }))
  await page.route('**/bag/v1.0/get/settings', async (route) => {
    const response = await route.fetch()
    const settings = response.ok() ? await response.json() : {}
    await route.fulfill({ json: { ...settings, is_pirate_mode: true, language: 'en' } })
  })
  // A fresh vehicle opens the setup wizard on every page load and the guided tour once
  await page.route('**/bag/v1.0/get/wizard', (route) => route.fulfill({ json: { version: 4 } }))
  await page.addLocatorHandler(page.getByRole('button', { name: 'Skip tour' }), (skip) => skip.click())
}

export const test = base.extend({
  page: async ({ page }, use) => {
    await preparePage(page)
    await use(page)
    // A test that ends fast closes the page while the settings route still waits on the vehicle
    await page.unrouteAll({ behavior: 'ignoreErrors' })
  },
})

export { expect }
